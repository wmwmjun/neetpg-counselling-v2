"""
All normalization logic: quota, category, state extraction, course.
Updated to match real MCC NEET-PG PDF values (2025 Round 1).
Each function is pure and testable.
"""
from __future__ import annotations
import re
import unicodedata
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# 3.1  Quota Normalization
# Real PDF quota codes as used by MCC NEET-PG 2025
# ---------------------------------------------------------------------------

# Canonical quota codes (norm values match what MCC actually uses)
QUOTA_MASTER = {
    "AIQ", "AMU", "BHU", "DU", "IP", "JM", "MM",
    "AFMS", "AFMS-DNB", "DNB Post MBBS", "MNG", "NBE Diploma", "NRI", "SFS", "JN",
}

_QUOTA_ALIAS: dict[str, str] = {
    # AIQ (All India Quota)
    "AIQ": "AIQ",
    "AI": "AIQ",
    "A.I.": "AIQ",
    "A.I.Q.": "AIQ",
    "ALL INDIA": "AIQ",
    "ALL INDIA QUOTA": "AIQ",
    # AMU (Aligarh Muslim University)
    "AMU": "AMU",
    "A.M.U.": "AMU",
    "AM": "AMU",
    "ALIGARH MUSLIM UNIVERSITY": "AMU",
    "ALIGARH MUSLIM UNIVERSITY QUOTA": "AMU",
    # BHU (Banaras Hindu University)
    "BHU": "BHU",
    "B.H.U.": "BHU",
    "BH": "BHU",
    "BANARAS HINDU UNIVERSITY": "BHU",
    "BANARAS HINDU UNIVERSITY QUOTA": "BHU",
    # DU (Delhi University)
    "DU": "DU",
    "D.U.": "DU",
    "DELHI UNIVERSITY": "DU",
    "DELHI UNIVERSITY QUOTA": "DU",
    # IP (IP University, Delhi)
    "IP": "IP",
    "I.P.": "IP",
    "IPCL": "IP",
    "IP UNIVERSITY": "IP",
    "IP UNIVERSITY QUOTA": "IP",
    "INDRAPRASTHA UNIVERSITY": "IP",
    # JM (Jamia Millia Islamia)
    "JM": "JM",
    "J.M.": "JM",
    "JAMIA": "JM",
    "JAMIA MILLIA ISLAMIA": "JM",
    "JAMIA MILLIA ISLAMIA QUOTA": "JM",
    # MM (Maulana Azad / Muslim Minority)
    "MM": "MM",
    "M.M.": "MM",
    "MUSLIM MINORITY": "MM",
    # AFMS (Armed Forces Medical Services)
    "AFMS": "AFMS",
    "AF": "AFMS",
    "A.F.": "AFMS",
    "A.F.M.S.": "AFMS",
    "ARMED FORCES": "AFMS",
    "ARMED FORCES MEDICAL SERVICES": "AFMS",
    # AFMS-DNB
    "AFMS-DNB": "AFMS-DNB",
    "AFMSDNB": "AFMS-DNB",
    # DNB
    "DNB POST MBBS": "DNB",
    "DNB-POST MBBS": "DNB",
    "AD": "DNB",
    "DNB": "DNB",
    "DNB QUOTA": "DNB",
    # MNG (Management quota)
    "MNG": "MNG",
    "MANAGEMENT": "MNG",
    "MGT": "MNG",
    "PS": "MNG",
    "MANAGEMENT QUOTA": "MNG",
    "MANAGEMENT/PAID SEATS QUOTA": "MNG",
    "MANAGEMENT/PAID SEATS": "MNG",
    "PAID SEATS QUOTA": "MNG",
    # NBE Diploma
    "NBE DIPLOMA": "NBE Diploma",
    "NBE-DIPLOMA": "NBE Diploma",
    "DIPLOMA": "NBE Diploma",
    # NRI
    "NRI": "NRI",
    "N.R.I.": "NRI",
    "NR": "NRI",
    "NRI QUOTA": "NRI",
    # SFS (Self-Financed Seat)
    "SFS": "SFS",
    "SELF FINANCED": "SFS",
    "SELF-FINANCED": "SFS",
    "SELF FINANCED MERIT SEAT": "SFS",
    "SELF-FINANCED MERIT SEAT": "SFS",
    "SELF FINANCED SEAT": "SFS",
    "SELF-FINANCED SEAT": "SFS",
    # SFS with "(Paid Seat Quota)" suffix as it appears in some PDFs
    "SELF-FINANCED MERIT SEAT/(PAID SEAT QUOTA)": "SFS",
    "SELF FINANCED MERIT SEAT/(PAID SEAT QUOTA)": "SFS",
    "SELF-FINANCED SEAT/(PAID SEAT QUOTA)": "SFS",
    "SELF FINANCED SEAT/(PAID SEAT QUOTA)": "SFS",
    # NRI full-form variants
    "NON-RESIDENT INDIAN": "NRI",
    "NON- RESIDENT INDIAN": "NRI",
    "NON RESIDENT INDIAN": "NRI",
    "NON RESIDENT INDIANS": "NRI",
    # Jain Minority (religious minority institution quota)
    "JAIN MINORITY": "JN",
    "JAIN MINORITY QUOTA": "JN",
    "JAIN": "JN",
    # Muslim Minority Quota (full-form alias for MM)
    "MUSLIM MINORITY QUOTA": "MM",
    # Armed Forces Medical (truncated form of AFMS)
    "ARMED FORCES MEDICAL": "AFMS",
    "ARMED FORCES MEDICAL SERVICES": "AFMS",
}


def normalize_quota(raw: Optional[str]) -> Tuple[str, bool]:
    """Returns (quota_norm, is_known)."""
    if not raw:
        return "UNKNOWN", False
    # Collapse newlines and multiple spaces before normalizing
    key = re.sub(r'[\r\n]+', ' ', raw.strip())
    key = re.sub(r'\s+', ' ', key).strip().upper()
    # Try direct lookup
    norm = _QUOTA_ALIAS.get(key)
    if norm:
        return norm, True
    # Try without spaces/hyphens/dots
    key2 = key.replace("-", "").replace(".", "").replace(" ", "")
    for alias, val in _QUOTA_ALIAS.items():
        if alias.replace("-", "").replace(".", "").replace(" ", "") == key2:
            return val, True
    return "UNKNOWN", False


# ---------------------------------------------------------------------------
# 3.2  Category Normalization
# Real PDF category codes as used by MCC NEET-PG 2025
# ---------------------------------------------------------------------------

_CATEGORY_ALIAS: dict[str, str] = {
    # General
    "GEN": "GEN",
    "GENERAL": "GEN",
    "UR": "GEN",
    "UNRESERVED": "GEN",
    "GN": "GEN",
    "OPEN": "GEN",
    # EWS
    "EWS": "EWS",
    "EW": "EWS",
    "E.W.S.": "EWS",
    # OBC
    "OBC": "OBC",
    "OBC-NCL": "OBC",
    "OBCNCL": "OBC",
    "BC": "OBC",
    "SEBC": "OBC",
    # SC
    "SC": "SC",
    # ST
    "ST": "ST",
    # PwD variants
    "GEN-PWD": "GEN-PwD",
    "GEN-PH": "GEN-PwD",
    "GEN-PwD": "GEN-PwD",
    "UR-PWD": "GEN-PwD",
    "UR-PH": "GEN-PwD",
    "OPEN PWD": "GEN-PwD",
    "OPEN PwD": "GEN-PwD",
    "OPEN PH": "GEN-PwD",
    "OPEN-PWD": "GEN-PwD",
    "OPEN-PwD": "GEN-PwD",
    "EWS-PWD": "EWS-PwD",
    "EWS-PH": "EWS-PwD",
    "EWS-PwD": "EWS-PwD",
    "EWS PWD": "EWS-PwD",
    "EWS PwD": "EWS-PwD",
    "EWS PH": "EWS-PwD",
    "OBC-PWD": "OBC-PwD",
    "OBC-PH": "OBC-PwD",
    "OBC-PwD": "OBC-PwD",
    "OBC PWD": "OBC-PwD",
    "OBC PwD": "OBC-PwD",
    "OBC PH": "OBC-PwD",
    "SC-PWD": "SC-PwD",
    "SC-PH": "SC-PwD",
    "SC-PwD": "SC-PwD",
    "SC PWD": "SC-PwD",
    "SC PwD": "SC-PwD",
    "SC PH": "SC-PwD",
    "ST-PWD": "ST-PwD",
    "ST-PH": "ST-PwD",
    "ST-PwD": "ST-PwD",
    "ST PWD": "ST-PwD",
    "ST PwD": "ST-PwD",
    "ST PH": "ST-PwD",
    # AFMS
    "AFMS-PRIORITY III": "AFMS-Priority III",
    "AFMS-PRIORITY-III": "AFMS-Priority III",
    "AFMS-P3": "AFMS-Priority III",
    "AFMS P3": "AFMS-Priority III",
    "AFMS PRIORITY III": "AFMS-Priority III",
    "AFMS-Priority III": "AFMS-Priority III",
    "AFMS-PRIORITY IV": "AFMS-Priority IV",
    "AFMS-PRIORITY-IV": "AFMS-Priority IV",
    "AFMS-P4": "AFMS-Priority IV",
    "AFMS P4": "AFMS-Priority IV",
    "AFMS PRIORITY IV": "AFMS-Priority IV",
    "AFMS-Priority IV": "AFMS-Priority IV",
}


def normalize_category(raw: Optional[str]) -> Tuple[str, bool]:
    """Returns (category_norm, is_known)."""
    if not raw:
        return "UNKNOWN", False
    # Collapse newlines and multiple spaces before normalizing
    key = re.sub(r'[\r\n]+', ' ', raw.strip())
    key = re.sub(r'\s+', ' ', key).strip()
    norm = _CATEGORY_ALIAS.get(key)
    if norm:
        return norm, True
    # Try uppercase
    key_upper = key.upper()
    norm = _CATEGORY_ALIAS.get(key_upper)
    if norm:
        return norm, True
    # Fuzzy match
    for alias, val in _CATEGORY_ALIAS.items():
        if alias.upper() == key_upper:
            return val, True
    return "UNKNOWN", False


# ---------------------------------------------------------------------------
# 3.3  State Extraction from institute text
# ---------------------------------------------------------------------------

INDIA_STATES: list[str] = [
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Dadra and Nagar Haveli",
    "Daman and Diu",
    "Delhi",
    "New Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jammu & Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Orissa",
    "Puducherry",
    "Pondicherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Tamilnadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "Uttaranchal",
    "West Bengal",
]

_STATE_CANONICAL: dict[str, str] = {
    "New Delhi": "Delhi",
    "Jammu & Kashmir": "Jammu and Kashmir",
    "Uttaranchal": "Uttarakhand",
    "Orissa": "Odisha",
    "Tamilnadu": "Tamil Nadu",
    "Pondicherry": "Puducherry",
    "Daman and Diu": "Dadra and Nagar Haveli and Daman and Diu",
    "Dadra and Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
}

_PINCODE_STATE: dict[str, str] = {
    "11": "Delhi", "110": "Delhi",
    "12": "Haryana", "13": "Haryana",
    "14": "Punjab", "15": "Punjab", "16": "Punjab",
    "17": "Himachal Pradesh",
    "18": "Jammu and Kashmir", "19": "Jammu and Kashmir",
    "20": "Uttar Pradesh", "21": "Uttar Pradesh", "22": "Uttar Pradesh",
    "23": "Uttar Pradesh", "24": "Uttar Pradesh", "25": "Uttar Pradesh",
    "26": "Uttar Pradesh", "27": "Uttar Pradesh", "28": "Uttar Pradesh",
    "30": "Rajasthan", "31": "Rajasthan", "32": "Rajasthan",
    "33": "Rajasthan", "34": "Rajasthan",
    "36": "Gujarat", "37": "Gujarat", "38": "Gujarat", "39": "Gujarat",
    "40": "Maharashtra", "41": "Maharashtra", "42": "Maharashtra",
    "43": "Maharashtra", "44": "Maharashtra",
    "45": "Madhya Pradesh", "46": "Madhya Pradesh", "47": "Madhya Pradesh",
    "48": "Madhya Pradesh", "49": "Chhattisgarh",
    "50": "Telangana", "51": "Telangana", "52": "Telangana",
    "53": "Andhra Pradesh",
    "56": "Karnataka", "57": "Karnataka", "58": "Karnataka", "59": "Karnataka",
    "60": "Tamil Nadu", "61": "Tamil Nadu", "62": "Tamil Nadu",
    "63": "Tamil Nadu", "64": "Tamil Nadu",
    "67": "Kerala", "68": "Kerala", "69": "Kerala",
    "70": "West Bengal", "71": "West Bengal", "72": "West Bengal",
    "73": "West Bengal", "74": "West Bengal",
    "75": "Odisha", "76": "Odisha", "77": "Odisha",
    "78": "Assam", "79": "Assam",
    "80": "Bihar", "81": "Bihar", "82": "Bihar", "83": "Bihar",
    "84": "Bihar", "85": "Bihar",
}


def extract_state_from_institute(institute_raw: Optional[str]) -> Optional[str]:
    if not institute_raw:
        return None
    text = institute_raw.strip()
    text_upper = text.upper()
    # Sort by length descending to prefer more specific matches
    for state in sorted(INDIA_STATES, key=len, reverse=True):
        if state.upper() in text_upper:
            return _STATE_CANONICAL.get(state, state)
    # Pincode inference
    for pin in re.findall(r'\b(\d{6})\b', text):
        for prefix in [pin[:3], pin[:2]]:
            if prefix in _PINCODE_STATE:
                return _PINCODE_STATE[prefix]
    return None


# Set of state names (uppercase) for quick lookup
_STATE_NAMES_UPPER: set[str] = {s.upper() for s in INDIA_STATES}
_STATE_NAMES_UPPER.update({v.upper() for v in _STATE_CANONICAL.values()})

# Generic address words to skip when scanning long address text for area names
_GENERIC_WORDS: set[str] = {
    'ROAD', 'STREET', 'NAGAR', 'COLONY', 'PLOT', 'SECTOR', 'BLOCK',
    'WARD', 'SURVEY', 'NEAR', 'OPPOSITE', 'OPP', 'MAIN', 'CROSS',
    'LANE', 'AVENUE', 'MARG', 'PHASE', 'FLOOR', 'BUILDING', 'POST',
    'DISTRICT', 'TALUK', 'TEHSIL', 'VILLAGE', 'TOWN', 'HOSPITAL',
    'MEDICAL', 'COLLEGE', 'INSTITUTE', 'UNIVERSITY', 'INDIA', 'BHARAT',
    'STATION', 'RAILWAY', 'JUNCTION', 'EAST', 'WEST', 'NORTH', 'SOUTH',
    'GATE', 'CHOWK', 'BAZAAR', 'BAZAR', 'MARKET', 'PARK', 'GARDEN',
}


def extract_pincode_from_institute(institute_raw: Optional[str]) -> Optional[str]:
    """Return the first 6-digit pincode found in the raw institute string."""
    if not institute_raw:
        return None
    pincodes = re.findall(r'\b(\d{6})\b', institute_raw)
    return pincodes[0] if pincodes else None


def _extract_area_from_long_text(text: str, name_words: set[str] | None = None) -> Optional[str]:
    """
    From a long address string, extract a meaningful area/neighbourhood name.
    Strategy: find Title-case words that aren't generic address words, state names,
    or words that appear in the institute name itself.
    Example:
      "Care Hospitals Road No1 Banjara Hills Hyderabad"
      (with name_words={"CARE","HOSPITAL"}) → "Banjara"
      "Survey NO 46 by 2 Ward no 150 Ambalipura Sarjapur Road Bangalore"
      → "Ambalipura"
    """
    base_skip = (name_words or set()) | _GENERIC_WORDS | _STATE_NAMES_UPPER
    # Also skip plural forms (e.g. "HOSPITALS" when "HOSPITAL" is generic)
    skip = base_skip | {w + 'S' for w in base_skip if not w.endswith('S')}
    words = re.findall(r"[A-Za-z']+", text)
    current: list[str] = []
    candidates: list[str] = []
    for word in words:
        w_up = word.upper()
        if (word[0].isupper() and len(word) > 3 and w_up not in skip):
            current.append(word)
        else:
            if current:
                candidates.append(' '.join(current))
            current = []
    if current:
        candidates.append(' '.join(current))

    for c in candidates:
        if c.upper() not in _STATE_NAMES_UPPER:
            # Return just the first word to keep the label short and clean
            return c.split()[0]
    return None


def extract_city_from_institute(institute_raw: Optional[str]) -> Optional[str]:
    """
    Extract a short city/area label from the raw institute string.

    Priority order:
      1. First comma-part after the name that is NOT a state name and is short/clean.
      2. Area name extracted from longer comma-parts via capitalized-word heuristic.
      3. 6-digit pincode as last-resort uniqueness token.

    Examples:
      "Manipal Hospital, Karnataka, Survey NO 46 Ambalipura Sarjapur Road 560102"
        → (skips "Karnataka" as state) → "Ambalipura"   [via pass 2]
      "MGM Medical College, Aurangabad, ..."
        → "Aurangabad"   [via pass 1]
    """
    if not institute_raw:
        return None

    # Strip email addresses
    text = re.sub(r'\S+@\S+', '', institute_raw.strip())

    # Capture pincodes before removing them (fallback)
    pincodes = re.findall(r'\b(\d{6})\b', text)

    # Remove pincodes from text so they don't pollute part scanning
    text = re.sub(r'\b\d{6}\b', '', text)

    parts = [p.strip() for p in text.split(',')]

    # Words in institute name (parts[0]) — used to avoid re-extracting the name itself
    name_words: set[str] = {
        w.upper() for w in re.findall(r"[A-Za-z']+", parts[0] if parts else "")
        if len(w) > 3
    }

    # Pass 1 — clean short token that isn't a state
    _ADDR_PREFIX = re.compile(
        r'^(plot|sector|block|door|flat|house|no\.|no |pin|survey|ward|ph\.|ph |near|opp|opposite)\b',
        re.IGNORECASE,
    )
    for part in parts[1:7]:
        part = part.strip().rstrip('.,;:')
        if not part or len(part) < 3:
            continue
        if not part[0].isalpha():           # must start with a letter (skip "#98", "(Formerly...)" etc.)
            continue
        if re.match(r'^\d', part):          # starts with digit (redundant but safe)
            continue
        if _ADDR_PREFIX.match(part):        # generic address prefix
            continue
        if part.upper() in _STATE_NAMES_UPPER:   # is a state name → skip
            continue
        if len(part) > 35:                  # too long for a plain city label
            continue
        return part

    # Pass 2 — scan longer parts for a meaningful area name (skip name words)
    for part in parts[1:9]:
        part = part.strip()
        if len(part) > 20:
            area = _extract_area_from_long_text(part, name_words)
            if area and area.upper() not in _STATE_NAMES_UPPER:
                return area

    # Pass 3 — pincode fallback (ensures uniqueness even when no area name found)
    if pincodes:
        return pincodes[0]

    return None


def clean_institute_name(institute_raw: Optional[str]) -> Optional[str]:
    if not institute_raw:
        return None
    text = institute_raw.strip()
    text = re.sub(r'\S+@\S+', '', text)
    text = re.sub(r'[\+\d][\d\s\-\(\)]{7,}', '', text)
    text = re.sub(r'\b\d{6}\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    parts = [p.strip() for p in re.split(r',', text) if p.strip()]
    if parts:
        name = parts[0].rstrip('.,;:')
        return name if len(name) > 3 else text
    return text


# ---------------------------------------------------------------------------
# 3.4  Course Normalization
# ---------------------------------------------------------------------------

_DEGREE_PATTERNS: list[Tuple[str, str]] = [
    (r'M\.?C\.?H\.?', 'MCH'),
    (r'D\.?N\.?B\.?', 'DNB'),
    (r'D\.?M\.?', 'DM'),
    (r'M\.?P\.?H\.?', 'MPH'),
    (r'M\.?D\.?', 'MD'),
    (r'M\.?S\.?', 'MS'),
    (r'M\.?B\.?B\.?S\.?', 'MBBS'),
    (r'M\.?Sc\.?', 'MSC'),
    (r'B\.?Sc\.?', 'BSC'),
    (r'DIPLOMA\s+IN', 'DIPLOMA'),
    (r'DIP\.?\s+IN', 'DIPLOMA'),
    (r'DIP\.?', 'DIPLOMA'),
    (r'MASTER\s+OF\s+PUBLIC\s+HEALTH', 'MPH'),
]

_KNOWN_DEGREES = ['MCH', 'DNB', 'DM', 'MPH', 'MD', 'MS', 'MBBS', 'MSC', 'BSC', 'DIPLOMA']

# ---------------------------------------------------------------------------
# Split-word fixes: PDF line-break artifacts produce inconsistent word splits
# (e.g. "VENEREOL OGY" in R1 vs "VENE REOLOGY" in R2 for the same specialty).
# These patterns are applied after basic normalization so that re-ingestion of
# any round always yields the same canonical course_norm.
# Each entry is (regex_pattern, replacement) — applied to the uppercased,
# whitespace-collapsed course string.
# ---------------------------------------------------------------------------
_SPLIT_WORD_FIXES: list[Tuple[str, str]] = [
    # Spaced-letter abbreviation: "E N T" → "ENT"
    (r'\bE N T\b', 'ENT'),
    # VENEREOLOGY splits
    (r'\bVENEREOL OGY\b', 'VENEREOLOGY'),
    (r'\bVENE REOLOGY\b', 'VENEREOLOGY'),
    # VENEREAL split
    (r'\bVENERE AL\b', 'VENEREAL'),
    # OPHTHALMOLOGY split
    (r'\bOPHTHALMOLOG Y\b', 'OPHTHALMOLOGY'),
    # DOMS (Diploma Ophthalmology) split
    (r'\bDOM S\b', 'DOMS'),
    # DERMATOLOGY split
    (r'\bDERMATOLO GY\b', 'DERMATOLOGY'),
    # LEPROSY split
    (r'\bLEPRO SY\b', 'LEPROSY'),
]


def normalize_course(raw: Optional[str]) -> str:
    if not raw:
        return ""
    text = unicodedata.normalize('NFKD', raw)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = text.upper()
    text = re.sub(r'[()]', ' ', text)
    text = re.sub(r'[\[\]]', ' ', text)
    for pattern, replacement in _DEGREE_PATTERNS:
        text = re.sub(r'\b' + pattern + r'\b', replacement, text)
    text = re.sub(r'\s*[-–—/]\s*', ' ', text)
    text = re.sub(r'[.,;:!?]', ' ', text)
    text = ' '.join(text.split())
    # Fix PDF line-break split-word artifacts (must run after whitespace collapse)
    for pattern, replacement in _SPLIT_WORD_FIXES:
        text = re.sub(pattern, replacement, text)
    return text


def split_course_degree_specialty(course_norm: str) -> Tuple[Optional[str], Optional[str]]:
    if not course_norm:
        return None, None
    for deg in _KNOWN_DEGREES:
        if course_norm.startswith(deg + ' '):
            return deg, course_norm[len(deg):].strip()
        if course_norm == deg:
            return deg, None
    return None, course_norm


# ---------------------------------------------------------------------------
# 3.5  Course Type Classification
# Clinical | Non-Clinical | Para-Clinical | Pre-Clinical
#
# Based on NMC/MCI classification of PG medical specialties:
#   Pre-Clinical  : Anatomy, Physiology, Biochemistry
#   Para-Clinical : Pathology, Microbiology, Pharmacology, Forensic Medicine,
#                   Community Medicine/SPM, Immuno-Haematology, Lab Medicine
#   Clinical      : All patient-facing specialties (Medicine, Surgery, etc.)
#   Non-Clinical  : Hospital Administration, Public Health, Health Admin,
#                   Biostatistics, Medical Education
# ---------------------------------------------------------------------------

# Specialty keywords → course_type  (checked against uppercased specialty string)
# Order matters: first match wins. More specific patterns come first.

_COURSE_TYPE_RULES: list[Tuple[str, str]] = [
    # ── Pre-Clinical ──
    ("ANATOMY", "Pre-Clinical"),
    ("PHYSIOLOGY", "Pre-Clinical"),
    ("BIO CHEMISTRY", "Pre-Clinical"),
    ("BIOCHEMISTRY", "Pre-Clinical"),

    # ── Para-Clinical ──
    ("PATHOLOGY", "Para-Clinical"),        # includes Clinical Pathology
    ("MICROBIOLOGY", "Para-Clinical"),
    ("PHARMACOLOGY", "Para-Clinical"),
    ("FORENSIC MEDICINE", "Para-Clinical"),
    ("FORENSIC", "Para-Clinical"),
    ("SOCIAL & PREVENTIVE", "Para-Clinical"),
    ("SOCIAL AND PREVENTIVE", "Para-Clinical"),
    ("COMMUNITY MEDICINE", "Para-Clinical"),
    ("COMMUNITY HEALTH", "Para-Clinical"),
    ("PREVENTIVE MEDICINE", "Para-Clinical"),
    ("IMMUNO HAEMATOLOGY", "Para-Clinical"),
    ("IMMUNO HEMATOLOGY", "Para-Clinical"),
    ("BLOOD TRANSFUSION", "Para-Clinical"),
    ("LAB MEDICINE", "Para-Clinical"),
    ("LABORATORY MEDICINE", "Para-Clinical"),
    ("TROPICAL MEDICINE", "Para-Clinical"),

    # ── Non-Clinical ──
    ("HOSPITAL ADMINISTRATION", "Non-Clinical"),
    ("HEALTH ADMINISTRATION", "Non-Clinical"),
    ("PUBLIC HEALTH", "Non-Clinical"),
    ("EPIDEMIOLOGY", "Non-Clinical"),
    ("BIOSTATISTICS", "Non-Clinical"),
    ("MEDICAL EDUCATION", "Non-Clinical"),
    ("AVIATION MEDICINE", "Non-Clinical"),
    ("AEROSPACE MEDICINE", "Non-Clinical"),

    # ── Clinical (everything else is clinical, but explicit patterns help) ──
    ("GENERAL MEDICINE", "Clinical"),
    ("GENERAL SURGERY", "Clinical"),
    ("PAEDIATRICS", "Clinical"),
    ("PEDIATRICS", "Clinical"),
    ("OBSTETRICS", "Clinical"),
    ("GYNAECOLOGY", "Clinical"),
    ("GYNECOLOGY", "Clinical"),
    ("OPHTHALMOLOGY", "Clinical"),
    ("ENT", "Clinical"),
    ("OTO RHINO LARYNGOLOGY", "Clinical"),
    ("OTORHINOLARYNGOLOGY", "Clinical"),
    ("ORTHOPAEDICS", "Clinical"),
    ("ORTHOPEDICS", "Clinical"),
    ("ORTHOPAEDIC", "Clinical"),
    ("TRAUMATOLOGY", "Clinical"),
    ("DERMATOLOGY", "Clinical"),
    ("VENEREOLOGY", "Clinical"),
    ("LEPROSY", "Clinical"),
    ("PSYCHIATRY", "Clinical"),
    ("PSYCHOLOGICAL MEDICINE", "Clinical"),
    ("ANAESTHESIOLOGY", "Clinical"),
    ("ANAESTHESIA", "Clinical"),
    ("ANESTHESIOLOGY", "Clinical"),
    ("ANESTHESIA", "Clinical"),
    ("RADIO DIAGNOSIS", "Clinical"),
    ("RADIODIAGNOSIS", "Clinical"),
    ("RADIOLOGY", "Clinical"),
    ("RADIATION ONCOLOGY", "Clinical"),
    ("RADIO THERAPY", "Clinical"),
    ("RADIOTHERAPY", "Clinical"),
    ("RADIATION MEDICINE", "Clinical"),
    ("NUCLEAR MEDICINE", "Clinical"),
    ("EMERGENCY MEDICINE", "Clinical"),
    ("FAMILY MEDICINE", "Clinical"),
    ("PHYSICAL MEDICINE", "Clinical"),
    ("REHABILITATION", "Clinical"),
    ("PALLIATIVE MEDICINE", "Clinical"),
    ("GERIATRICS", "Clinical"),
    ("GERIATRIC MEDICINE", "Clinical"),
    ("SPORTS MEDICINE", "Clinical"),
    ("RESPIRATORY DISEASES", "Clinical"),
    ("TUBERCULOSIS", "Clinical"),
    ("CHEST DISEASES", "Clinical"),
    ("CHILD HEALTH", "Clinical"),
    ("DIABETOLOGY", "Clinical"),
    ("NEUROSURGERY", "Clinical"),
    ("NEURO SURGERY", "Clinical"),
    ("CARDIO THORACIC SURGERY", "Clinical"),
    ("PLASTIC SURGERY", "Clinical"),
    ("PAEDIATRIC SURGERY", "Clinical"),
    ("PEDIATRIC SURGERY", "Clinical"),
]


def classify_course_type(course_norm: str) -> str:
    """
    Classify a normalized course name into one of the four course types.
    Returns: "Clinical" | "Non-Clinical" | "Para-Clinical" | "Pre-Clinical"
    Defaults to "Clinical" if no specific rule matches (safe default for
    medical PG courses).
    """
    if not course_norm:
        return "Clinical"
    upper = course_norm.upper()
    for keyword, course_type in _COURSE_TYPE_RULES:
        if keyword in upper:
            return course_type
    # Default: most PG medical courses are clinical
    return "Clinical"
