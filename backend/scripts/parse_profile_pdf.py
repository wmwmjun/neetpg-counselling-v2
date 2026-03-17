"""
Parse Profile Combined PDF to extract Annual Fee and Stipend data for all institutes.
Each profile is 2 pages (ANNEXURE-C format). Page 1 is cover page.
"""
import re, json, sqlite3, os
from pypdf import PdfReader

PDF_PATH = "/sessions/cool-eloquent-davinci/mnt/uploads/Profile Combined (17.02.2026).pdf"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "neetpg.db")

reader = PdfReader(PDF_PATH)
total_pages = len(reader.pages)
print(f"PDF pages: {total_pages}")

# Parse patterns
RE_COLLEGE = re.compile(r"Name of the College:\s*(.+?)(?:\n|Complete)", re.DOTALL)
RE_STATE = re.compile(r"State:\s*(\d+)")
RE_PIN = re.compile(r"Pin Code:\s*(\d+)")
RE_ANNUAL_FEE = re.compile(r"Annual Fees? of Candidates?\s*\(INR\)\s*:?\s*(\S+)")
RE_STIPEND1 = re.compile(r"Stipend Paid to the students?\s*I\s*st\s*Year\s*\(INR\)\s*:?\s*(\S+)")
RE_STIPEND2 = re.compile(r"Stipend Paid to the students?\s*IInd\s*Year\s*\(INR\)\s*:?\s*(\S+)")
RE_STIPEND3 = re.compile(r"Stipend Paid to the students?\s*IIIrd\s*Year\s*\(INR\)\s*:?\s*(\S+)")
RE_BOND_FORFEIT = re.compile(
    r"Amount to be forfeited in case of\s*resigning.*?Round of counselling period \(INR\)\s*:?\s*(\S+)",
    re.DOTALL
)

def clean_num(s):
    if not s or s.lower() in ('na', 'n/a', '-', 'nil', 'none', ''):
        return None
    s = s.replace(',', '').replace('₹', '').replace(' ', '').strip()
    try:
        val = float(s)
        return val
    except ValueError:
        return None

def is_numeric_text(s):
    if not s:
        return False
    s = s.replace(',', '').replace('.', '', 1).strip()
    return s.isdigit()

profiles = []
page_idx = 1  # skip cover page

while page_idx < total_pages:
    # Each profile spans 2 pages (sometimes text flows)
    text = ""
    # Get 2 pages for each profile
    for offset in range(min(2, total_pages - page_idx)):
        text += reader.pages[page_idx + offset].extract_text() or ""
        text += "\n"

    # Check if this looks like a profile page
    if "ANNEXURE" not in text and "Name of the College" not in text:
        page_idx += 1
        continue

    # Extract fields
    college_match = RE_COLLEGE.search(text)
    college_name = college_match.group(1).strip() if college_match else None

    if not college_name:
        page_idx += 2
        continue

    state_match = RE_STATE.search(text)
    pin_match = RE_PIN.search(text)
    annual_fee_match = RE_ANNUAL_FEE.search(text)
    stipend1_match = RE_STIPEND1.search(text)
    stipend2_match = RE_STIPEND2.search(text)
    stipend3_match = RE_STIPEND3.search(text)
    bond_match = RE_BOND_FORFEIT.search(text)

    profile = {
        "college_name": college_name,
        "state_code": state_match.group(1) if state_match else None,
        "pincode": pin_match.group(1) if pin_match else None,
        "annual_fee": clean_num(annual_fee_match.group(1)) if annual_fee_match else None,
        "stipend_yr1": clean_num(stipend1_match.group(1)) if stipend1_match else None,
        "stipend_yr2": clean_num(stipend2_match.group(1)) if stipend2_match else None,
        "stipend_yr3": clean_num(stipend3_match.group(1)) if stipend3_match else None,
        "bond_forfeit": clean_num(bond_match.group(1)) if bond_match else None,
    }
    profiles.append(profile)
    page_idx += 2

print(f"Parsed {len(profiles)} profiles")

# Stats
has_annual = sum(1 for p in profiles if p['annual_fee'] is not None)
has_stip1 = sum(1 for p in profiles if p['stipend_yr1'] is not None)
has_stip2 = sum(1 for p in profiles if p['stipend_yr2'] is not None)
has_stip3 = sum(1 for p in profiles if p['stipend_yr3'] is not None)
has_bond = sum(1 for p in profiles if p['bond_forfeit'] is not None)
print(f"Annual Fee: {has_annual}, Stipend Y1: {has_stip1}, Y2: {has_stip2}, Y3: {has_stip3}, Bond: {has_bond}")

# Sample output
for p in profiles[:3]:
    print(f"  {p['college_name'][:50]} | fee={p['annual_fee']} | stip={p['stipend_yr1']}/{p['stipend_yr2']}/{p['stipend_yr3']} | bond={p['bond_forfeit']}")

# Save JSON for debugging
with open("/tmp/parsed_profiles.json", "w") as f:
    json.dump(profiles, f, indent=2, ensure_ascii=False)
print("Saved /tmp/parsed_profiles.json")

# Now match to institutes table and update DB
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Build lookup: college_name -> profile data
# Profiles use the MCC college name, institutes table uses Seat Matrix name
# We need to go through profiles_v2.csv matching (college_name -> institute_code via matched_institutes_v3.csv)
import csv

# Load matched_institutes_v3.csv for the mapping
matched_csv = "/tmp/matched_institutes_v3.csv"
if os.path.exists(matched_csv):
    with open(matched_csv, "r") as f:
        matched_rows = list(csv.DictReader(f))

    # Build: profile_name -> institute_code
    prof_to_code = {}
    for mr in matched_rows:
        pname = mr.get("profile_name", "").strip()
        code = mr.get("institute_code", "")
        if pname and code:
            prof_to_code[pname] = int(code)

    print(f"Profile->Code mappings: {len(prof_to_code)}")

    # Build: college_name (from PDF) -> profile data
    # PDF college names should match profiles_v2.csv college_name
    pdf_map = {}
    for p in profiles:
        name = p["college_name"].strip().upper()
        pdf_map[name] = p
        # Also store with original case
        pdf_map[p["college_name"].strip()] = p

    updated = 0
    for prof_name, code in prof_to_code.items():
        # Try exact match first
        profile = pdf_map.get(prof_name) or pdf_map.get(prof_name.upper())
        if not profile:
            # Try fuzzy: strip and compare
            for pname, pdata in pdf_map.items():
                if pname.upper().replace(",", "").replace(".", "") == prof_name.upper().replace(",", "").replace(".", ""):
                    profile = pdata
                    break

        if not profile:
            continue

        annual_fee = profile["annual_fee"]
        stip1 = profile["stipend_yr1"]
        stip2 = profile["stipend_yr2"]
        stip3 = profile["stipend_yr3"]

        # Convert stipend to string for DB (stored as TEXT)
        stip1_str = str(int(stip1)) if stip1 is not None else None
        stip2_str = str(int(stip2)) if stip2 is not None else None
        stip3_str = str(int(stip3)) if stip3 is not None else None

        cur.execute("""
            UPDATE institutes SET
                annual_fee = ?,
                stipend_yr1 = ?,
                stipend_yr2 = ?,
                stipend_yr3 = ?
            WHERE institute_code = ?
        """, (
            str(int(annual_fee)) if annual_fee is not None else None,
            stip1_str, stip2_str, stip3_str,
            code
        ))
        if cur.rowcount > 0:
            updated += 1

    conn.commit()
    print(f"Updated {updated} institutes in DB")

# Verify
cur.execute("SELECT COUNT(*) FROM institutes WHERE annual_fee IS NOT NULL AND annual_fee != ''")
print(f"Institutes with annual_fee: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM institutes WHERE stipend_yr1 IS NOT NULL AND stipend_yr1 != ''")
print(f"Institutes with stipend_yr1: {cur.fetchone()[0]}")

# Show some samples
cur.execute("SELECT institute_name, annual_fee, stipend_yr1, stipend_yr2, stipend_yr3 FROM institutes WHERE annual_fee IS NOT NULL LIMIT 5")
for r in cur.fetchall():
    print(f"  {r[0][:40]} | fee={r[1]} | stip={r[2]}/{r[3]}/{r[4]}")

conn.close()
