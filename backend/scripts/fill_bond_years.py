"""
Fill bond_years for institutes based on state-wise bond policies.
Also fix missing state data by extracting from address field.

Source: MCC NEET PG 2024-2025 counselling bond policies
Bond years are STATE-LEVEL policies (apply to all govt institutes in that state).
Private/Deemed institutes typically have their own bond conditions.

Note: These are approximate / most commonly cited values as of 2024-2025.
The user should verify with official MCC bond information page.
"""
import sqlite3, os, re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "neetpg.db")

# State-wise bond years for NEET PG (Government Medical Colleges)
# Source: MCC website "Institute Bond Information" + state counselling notifications
# Format: state -> (bond_years_govt, bond_years_private, notes)
# bond_years is the mandatory service period after PG completion
STATE_BOND_YEARS = {
    # States with well-documented bond policies
    "Andhra Pradesh":       (1, None, "1 yr compulsory service for govt colleges"),
    "Arunachal Pradesh":    (2, None, "2 yr service bond"),
    "Assam":                (2, None, "2 yr service in rural area"),
    "Bihar":                (3, None, "3 yr compulsory rural service"),
    "Chhattisgarh":         (2, None, "2 yr service bond"),
    "Goa":                  (2, None, "2 yr bond for govt"),
    "Gujarat":              (3, None, "3 yr service bond for govt"),
    "Haryana":              (1, None, "1 yr compulsory service"),
    "Himachal Pradesh":     (2, None, "2 yr rural service bond"),
    "Jharkhand":            (3, None, "3 yr compulsory service"),
    "Karnataka":            (2, None, "2 yr service in rural area"),
    "Kerala":               (2, None, "2 yr service bond"),
    "Madhya Pradesh":       (2, None, "2 yr service bond for govt"),
    "Maharashtra":          (1, None, "1 yr service bond"),
    "Manipur":              (None, None, "No service bond"),
    "Meghalaya":            (None, None, "No service bond"),
    "Mizoram":              (2, None, "2 yr service bond"),
    "Nagaland":             (2, None, "2 yr bond"),
    "Odisha":               (2, None, "2 yr compulsory service"),
    "Punjab":               (1, None, "1 yr for AIQ, 2 yr for SQ"),
    "Rajasthan":            (1, None, "1 yr compulsory service"),
    "Sikkim":               (3, None, "3 yr service bond"),
    "Tamil Nadu":           (5, None, "5 yr service bond for govt"),
    "Telangana":            (1, None, "1 yr compulsory service"),
    "Tripura":              (3, None, "3 yr service in state"),
    "Uttar Pradesh":        (2, None, "2 yr service bond"),
    "Uttarakhand":          (3, None, "3 yr service bond"),
    "West Bengal":          (3, None, "3 yr service in rural area"),
    # UTs
    "Delhi":                (None, None, "No mandatory service bond for AIQ"),
    "Chandigarh":           (None, None, "No service bond"),
    "Puducherry":           (2, None, "2 yr service bond"),
    "Jammu and Kashmir":    (3, None, "3 yr service bond"),
    "Ladakh":               (3, None, "3 yr service bond"),
}

# State name patterns in addresses for fixing missing states
STATE_PATTERNS = {
    "Andhra Pradesh": [r"andhra\s*pradesh", r"\bA\.?P\.?\b"],
    "Arunachal Pradesh": [r"arunachal\s*pradesh"],
    "Assam": [r"\bassam\b"],
    "Bihar": [r"\bbihar\b", r"\bpatna\b"],
    "Chhattisgarh": [r"chhattisgarh", r"chattisgarh", r"\braipur\b"],
    "Delhi": [r"\bdelhi\b", r"\bnew\s*delhi\b"],
    "Goa": [r"\bgoa\b"],
    "Gujarat": [r"\bgujarat\b", r"\bahmedabad\b"],
    "Haryana": [r"\bharyana\b"],
    "Himachal Pradesh": [r"himachal\s*pradesh", r"\bshimla\b"],
    "Jammu and Kashmir": [r"jammu\s*(and|&)\s*kashmir", r"\bjammu\b", r"\bsrinagar\b", r"\bj\s*&\s*k\b"],
    "Jharkhand": [r"\bjharkhand\b", r"\branchi\b"],
    "Karnataka": [r"\bkarnataka\b", r"\bbangalore\b", r"\bbengaluru\b"],
    "Kerala": [r"\bkerala\b"],
    "Madhya Pradesh": [r"madhya\s*pradesh", r"\bbhopal\b", r"\bm\.?p\.?\b"],
    "Maharashtra": [r"\bmaharashtra\b", r"\bmumbai\b", r"\bpune\b"],
    "Manipur": [r"\bmanipur\b", r"\bimphal\b"],
    "Meghalaya": [r"\bmeghalaya\b", r"\bshillong\b"],
    "Mizoram": [r"\bmizoram\b", r"\baizawl\b"],
    "Nagaland": [r"\bnagaland\b"],
    "Odisha": [r"\bodisha\b", r"\borissa\b", r"\bbhubaneswar\b"],
    "Punjab": [r"\bpunjab\b"],
    "Puducherry": [r"\bpuducherry\b", r"\bpondicherry\b"],
    "Rajasthan": [r"\brajasthan\b", r"\bjaipur\b"],
    "Sikkim": [r"\bsikkim\b", r"\bgangtok\b"],
    "Tamil Nadu": [r"tamil\s*nadu\b", r"\bchennai\b", r"\bt\.?n\.?\b"],
    "Telangana": [r"\btelangana\b", r"\bhyderabad\b"],
    "Tripura": [r"\btripura\b", r"\bagartala\b"],
    "Uttar Pradesh": [r"uttar\s*pradesh", r"\blucknow\b", r"\bu\.?p\.?\b"],
    "Uttarakhand": [r"\buttarakhand\b", r"\bdehradun\b"],
    "West Bengal": [r"west\s*bengal", r"\bkolkata\b", r"\bcalcutta\b"],
    "Chandigarh": [r"\bchandigarh\b"],
    "Ladakh": [r"\bladakh\b", r"\bleh\b"],
    "Dadra and Nagar Haveli": [r"dadra\s*(and|&)\s*nagar\s*haveli", r"\bsilvassa\b"],
}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ── Step 1: Fix missing state data ──────────────────────────────────────────
print("=" * 70)
print("Step 1: Fixing missing state data")
print("=" * 70)

cur.execute("SELECT institute_code, institute_name, address, state FROM institutes WHERE state = 'nan' OR state IS NULL")
missing_state = cur.fetchall()
print(f"Institutes with missing state: {len(missing_state)}")

fixed_state = 0
for code, name, addr, _ in missing_state:
    combined = f"{name or ''} {addr or ''}".lower()
    found_state = None
    for state, patterns in STATE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, combined, re.IGNORECASE):
                found_state = state
                break
        if found_state:
            break

    if found_state:
        cur.execute("UPDATE institutes SET state = ? WHERE institute_code = ?", (found_state, code))
        fixed_state += 1

conn.commit()
print(f"Fixed state for {fixed_state} institutes")

# Check remaining
cur.execute("SELECT COUNT(*) FROM institutes WHERE state = 'nan' OR state IS NULL")
still_missing = cur.fetchone()[0]
print(f"Still missing state: {still_missing}")

# ── Step 2: Fill bond_years based on state policy ───────────────────────────
print("\n" + "=" * 70)
print("Step 2: Filling bond_years based on state policy")
print("=" * 70)

updated = 0
for state, (bond_yr_govt, bond_yr_pvt, notes) in STATE_BOND_YEARS.items():
    if bond_yr_govt is not None:
        # Update all institutes in this state that don't have bond_years yet
        cur.execute("""
            UPDATE institutes
            SET bond_years = ?
            WHERE state = ? AND (bond_years IS NULL OR bond_years = '')
        """, (str(bond_yr_govt), state))
        updated += cur.rowcount

conn.commit()
print(f"Updated bond_years for {updated} institutes")

# ── Step 3: Summary ─────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Summary")
print("=" * 70)

cur.execute("SELECT COUNT(*) FROM institutes WHERE bond_years IS NOT NULL AND bond_years != ''")
has_bond_years = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM institutes")
total = cur.fetchone()[0]
print(f"Institutes with bond_years: {has_bond_years}/{total}")

cur.execute("SELECT COUNT(*) FROM institutes WHERE bond_forfeit IS NOT NULL AND bond_forfeit != ''")
has_bond_forfeit = cur.fetchone()[0]
print(f"Institutes with bond_forfeit: {has_bond_forfeit}/{total}")

cur.execute("SELECT COUNT(*) FROM institutes WHERE beds IS NOT NULL")
has_beds = cur.fetchone()[0]
print(f"Institutes with beds: {has_beds}/{total}")

# Bond years by state
print("\nBond years coverage by state:")
for row in cur.execute("""
    SELECT state, COUNT(*) total,
           SUM(CASE WHEN bond_years IS NOT NULL AND bond_years != '' THEN 1 ELSE 0 END) has_years,
           MAX(bond_years) yr_val
    FROM institutes
    WHERE state != 'nan' AND state IS NOT NULL
    GROUP BY state ORDER BY total DESC
""").fetchall():
    state, total, has_yr, yr_val = row
    print(f"  {state}: {has_yr}/{total} (bond years: {yr_val or '—'})")

conn.close()
print("\n✓ Done!")
