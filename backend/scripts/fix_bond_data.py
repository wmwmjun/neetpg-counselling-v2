"""
Fix bond_forfeit data in institutes table:
1. Recover 223 entries where bond_forfeit=0.0 was lost due to safe_str bug
2. Recover bond data for non-EXACT matched institutes (PIN_MISMATCH, PIN_AMBIG, etc.)
3. Add bond_years and beds columns to the schema
"""
import sqlite3, os, math
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "neetpg.db")
MATCHED_CSV = "/tmp/matched_institutes_v3.csv"

print("=" * 70)
print("Fix bond_forfeit data in institutes table")
print("=" * 70)

# Load matched CSV (has prof_bond_forfeit for all match statuses)
matched = pd.read_csv(MATCHED_CSV)
print(f"Loaded {len(matched)} rows from matched CSV")

# Build institute_code -> bond_forfeit map from ALL matched rows with bond data
# (not just EXACT - includes PIN_MISMATCH, PIN_AMBIG, FUZZY, etc.)
bond_map = {}
for _, row in matched.iterrows():
    code = int(row['institute_code'])
    bond = row.get('prof_bond_forfeit')
    if pd.notna(bond):
        bond_map[code] = str(bond)

print(f"Institutes with bond data in matched CSV: {len(bond_map)}")

# Also collect other profile data that might have been lost
fee_map = {}  # institute_code -> {fee_yr1, fee_yr2, fee_yr3, stipend_yr1, ...}
for _, row in matched.iterrows():
    code = int(row['institute_code'])
    data = {}
    for col in ['fee_yr1', 'fee_yr2', 'fee_yr3', 'stipend_yr1', 'stipend_yr2', 'stipend_yr3',
                'hostel_male', 'hostel_female', 'university', 'pwbd_friendly', 'website', 'annual_fee']:
        val = row.get(f'prof_{col}')
        if pd.notna(val):
            data[col] = val
    if data:
        fee_map[code] = data

# Connect to DB
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Step 1: Add bond_years and beds columns if they don't exist
existing_cols = [r[1] for r in cur.execute("PRAGMA table_info(institutes)").fetchall()]
print(f"\nExisting columns: {existing_cols}")

if 'bond_years' not in existing_cols:
    cur.execute("ALTER TABLE institutes ADD COLUMN bond_years TEXT")
    print("Added bond_years column")

if 'beds' not in existing_cols:
    cur.execute("ALTER TABLE institutes ADD COLUMN beds INTEGER")
    print("Added beds column")

conn.commit()

# Step 2: Update bond_forfeit for all institutes that have data in matched CSV
updated_bond = 0
updated_other = 0
for code, bond_val in bond_map.items():
    # Check if this institute exists in DB
    existing = cur.execute("SELECT bond_forfeit FROM institutes WHERE institute_code = ?", (code,)).fetchone()
    if existing is None:
        continue

    current_bond = existing[0]
    if current_bond is None or current_bond == '':
        cur.execute("UPDATE institutes SET bond_forfeit = ? WHERE institute_code = ?", (bond_val, code))
        updated_bond += 1

# Also fill in any other missing profile data
for code, data in fee_map.items():
    existing = cur.execute("SELECT * FROM institutes WHERE institute_code = ?", (code,)).fetchone()
    if existing is None:
        continue

    col_idx = {col[1]: i for i, col in enumerate(cur.execute("PRAGMA table_info(institutes)").fetchall())}

    updates = []
    for col, val in data.items():
        if col in col_idx:
            current = existing[col_idx[col]]
            if current is None or current == '':
                if col in ('fee_yr1', 'fee_yr2', 'fee_yr3'):
                    try:
                        val = float(val)
                    except:
                        continue
                else:
                    val = str(val)
                updates.append((col, val))

    if updates:
        set_clause = ", ".join(f"{col} = ?" for col, _ in updates)
        vals = [v for _, v in updates] + [code]
        cur.execute(f"UPDATE institutes SET {set_clause} WHERE institute_code = ?", vals)
        updated_other += 1

conn.commit()

print(f"\nUpdated bond_forfeit for {updated_bond} institutes")
print(f"Updated other profile data for {updated_other} institutes")

# Step 3: Verify
cur.execute("SELECT COUNT(*) FROM institutes WHERE bond_forfeit IS NOT NULL AND bond_forfeit != ''")
total_bond = cur.fetchone()[0]
print(f"\nTotal institutes with bond_forfeit now: {total_bond}")

# Bond value distribution
cur.execute("""
    SELECT
        CASE
            WHEN CAST(bond_forfeit AS REAL) = 0 THEN 'Zero (no bond)'
            WHEN CAST(bond_forfeit AS REAL) > 0 THEN 'Has penalty'
            ELSE 'Non-numeric'
        END as category,
        COUNT(*)
    FROM institutes
    WHERE bond_forfeit IS NOT NULL AND bond_forfeit != ''
    GROUP BY category
""")
print("\nBond value distribution:")
for cat, cnt in cur.fetchall():
    print(f"  {cat}: {cnt}")

# Remaining gap
cur.execute("SELECT COUNT(*) FROM institutes WHERE bond_forfeit IS NULL OR bond_forfeit = ''")
missing = cur.fetchone()[0]
print(f"\nStill missing bond data: {missing}/{cur.execute('SELECT COUNT(*) FROM institutes').fetchone()[0]}")

conn.close()
print("\n✓ Done!")
