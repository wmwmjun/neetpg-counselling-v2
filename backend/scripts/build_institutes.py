import sqlite3, re

DB = "data/neetpg.db"

STATES_SET = {
    "andhra pradesh","arunachal pradesh","assam","bihar","chhattisgarh","goa","gujarat",
    "haryana","himachal pradesh","jharkhand","karnataka","kerala","madhya pradesh",
    "maharashtra","manipur","meghalaya","mizoram","nagaland","odisha","punjab",
    "rajasthan","sikkim","tamil nadu","telangana","tripura","uttar pradesh",
    "uttarakhand","west bengal","puducherry","pondicherry","delhi",
    "jammu and kashmir","jammu & kashmir","ladakh","chandigarh",
    "andaman and nicobar islands","andaman and nicobar","andaman & nicobar islands",
    "andaman & nicobar","andaman","nicobar",
    "dadra and nagar haveli","daman and diu","lakshadweep",
}
def is_state(s):  return s.strip().lower() in STATES_SET
def is_pincode(s): return bool(re.match(r'^\d{6}$', s.strip()))

def dedup_segs(segs):
    """If second half of segs repeats first half (roughly), return first half only."""
    n = len(segs)
    if n < 4: return segs
    for split in range(2, n // 2 + 1):
        first = [re.sub(r'[-\s]+', '', s.lower()) for s in segs[:split]]
        second = [re.sub(r'[-\s]+', '', s.lower()) for s in segs[split:split+split]]
        if first == second:
            return segs[:split]
    return segs

def clean_raw(inst_name: str, raw: str) -> str:
    if not raw:
        return ""

    # Remove institute name prefix from start
    name_esc = re.escape(inst_name.strip())
    after = re.sub(r'^' + name_esc + r'\s*[,\s]*', '', raw, count=1, flags=re.IGNORECASE)
    after = after.strip().lstrip(',').strip()

    # If first segment (before first comma) is a state name, remove it
    first_comma = after.find(',')
    if first_comma > 0:
        first_seg = after[:first_comma].strip()
        if is_state(first_seg):
            after = after[first_comma+1:].strip()

    # Split segments
    segs = [s.strip() for s in after.split(',')]

    clean = []
    for seg in segs:
        if not seg: continue
        if is_pincode(seg): continue
        # "State-424001" or "State 600077"
        seg_no_pin = re.sub(r'[-\s]+\d{4,6}\s*$', '', seg).strip()
        if is_state(seg_no_pin): continue
        # Skip if segment matches institute name (alternate casing)
        if seg.strip().lower() == inst_name.strip().lower(): continue
        # Skip trivial artifacts
        if re.match(r'^[.\s]*$', seg): continue
        if re.match(r'^[A-Z]{1,3}$', seg): continue
        clean.append(seg)

    # Deduplicate repeated address segments
    clean = dedup_segs(clean)

    result = ', '.join(clean)
    result = re.sub(r',?\s*\d{6}\s*$', '', result).strip(', ')
    result = re.sub(r'  +', ' ', result)
    return result.strip(', ')


conn = sqlite3.connect(DB)
cur = conn.cursor()

# Get best raw per institute: prefer R1, pick the longest
cur.execute("""
    SELECT institute_name, institute_pincode, state, institute_city,
           MAX(CASE WHEN round=1 THEN institute_raw ELSE '' END) AS r1_raw,
           MAX(institute_raw) AS best_raw
    FROM allotments
    WHERE institute_name IS NOT NULL
    GROUP BY institute_name
""")
rows = cur.fetchall()

cur.execute("DROP TABLE IF EXISTS institutes")
cur.execute("""
    CREATE TABLE institutes (
        institute_name  VARCHAR(256) PRIMARY KEY,
        clean_address   TEXT,
        pincode         VARCHAR(10),
        city            VARCHAR(128),
        state           VARCHAR(64)
    )
""")

inserted, empty_addr = 0, 0
for name, pincode, state, city, r1_raw, best_raw in rows:
    if not name: continue
    raw = r1_raw if (r1_raw and len(r1_raw.strip()) > 20) else (best_raw or "")
    cleaned = clean_raw(name, raw)
    cur.execute("INSERT OR REPLACE INTO institutes VALUES (?, ?, ?, ?, ?)",
                (name, cleaned, pincode, city, state))
    inserted += 1
    if not cleaned: empty_addr += 1

conn.commit()
print(f"Inserted {inserted} institutes, {empty_addr} with empty addresses")
print()

# Spot-check key cases
names = ['A C P M Medical College','AMAR HOSPITAL','APOLLO PROTON CANCER CENTRE',
         'AAKASH HOSPITAL','A.G.Padmavatis Hospital Ltd','AARTHI SCANS PVT LTD',
         'ANTARA PSYCHIATRIC HOSPITAL','AMRI Hospitals Ltd','7 Air Force Hospital',
         'AARUPADAI VEEDU MEDICAL COLLEGE AND HOSPITAL','ADK Jain Eye Hospital']
cur.execute("SELECT institute_name, clean_address, pincode FROM institutes WHERE institute_name IN ({})".format(
    ','.join('?'*len(names))), names)
for r in cur.fetchall():
    print(f"{r[0][:42]:42s} | {r[2]:6s} | {r[1][:80] if r[1] else '(EMPTY)'}")
conn.close()
