"""
All normalization logic: quota, category, state extraction, course.
Each function is pure and testable.
"""
from __future__ import annotations
import re
import unicodedata
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# 3.1  Quota Master
# ---------------------------------------------------------------------------

QUOTA_MASTER = {"AI", "AM", "BH", "DU", "AD", "IP", "JM", "MM", "NR", "PS"}

# Extended alias map  raw_upper → norm
_QUOTA_ALIAS: dict[str, str] = {
    "AI": "AI",
    "A.I.": "AI",
    "A.I": "AI",
    "AM": "AM",
    "A.M.": "AM",
    "BH": "BH",
    "BIHAR": "BH",
    "DU": "DU",
    "D.U.": "DU",
    "DELHI UNIVERSITY": "DU",
    "AD": "AD",
    "IP": "IP",
    "I.P.": "IP",
    "IPCL": "IP",
    "JM": "JM",
    "J.M.": "JM",
    "JAMIA": "JM",
    "MM": "MM",
    "M.M.": "MM",
    "NR": "NR",
    "NRI": "NR",
    "N.R.I.": "NR",
    "PS": "PS",
}


def normalize_quota(raw: Optional[str]) -> Tuple[str, bool]:
    """
    Returns (quota_norm, is_known).
    is_known=False → log as unknown.
    """
    if not raw:
        return "UNKNOWN", False
    key = raw.strip().upper().replace(" ", "")
    norm = _QUOTA_ALIAS.get(key)
    if norm:
        return norm, True
    # Partial match fallback
    for alias, val in _QUOTA_ALIAS.items():
        if key.startswith(alias) or alias.startswith(key):
            return val, True
    return "UNKNOWN", False


# ---------------------------------------------------------------------------
# 3.2  Category Master
# ---------------------------------------------------------------------------

_CATEGORY_ALIAS: dict[str, str] = {
    # General
    "UR": "GN",
    "GEN": "GN",
    "GENERAL": "GN",
    "UNRESERVED": "GN",
    "GN": "GN",
    "OPEN": "GN",
    # EWS
    "EWS": "EW",
    "EW": "EW",
    "E.W.S.": "EW",
    # OBC
    "OBC": "BC",
    "OBC-NCL": "BC",
    "OBCNCL": "BC",
    "BC": "BC",
    "SEBC": "BC",
    "MBC": "BC",
    # SC
    "SC": "SC",
    # ST
    "ST": "ST",
    # PwD variants
    "UR-PH": "GN-PwD",
    "GN-PH": "GN-PwD",
    "URPH": "GN-PwD",
    "UR-PWD": "GN-PwD",
    "GN-PWD": "GN-PwD",
    "OBC-PH": "BC-PwD",
    "OBC-PWD": "BC-PwD",
    "OBCPH": "BC-PwD",
    "EWS-PH": "EW-PwD",
    "EWS-PWD": "EW-PwD",
    "EW-PH": "EW-PwD",
    "EW-PWD": "EW-PwD",
    "SC-PH": "SC-PwD",
    "SC-PWD": "SC-PwD",
    "ST-PH": "ST-PwD",
    "ST-PWD": "ST-PwD",
}


def normalize_category(raw: Optional[str]) -> Tuple[str, bool]:
    """Returns (category_norm, is_known)."""
    if not raw:
        return "UNKNOWN", False
    key = raw.strip().upper().replace(" ", "").replace("-", "-")
    norm = _CATEGORY_ALIAS.get(key)
    if norm:
        return norm, True
    # Try stripping hyphens for lookup
    key2 = key.replace("-", "")
    for alias, val in _CATEGORY_ALIAS.items():
        if alias.replace("-", "") == key2:
            return val, True
    return "UNKNOWN", False


# ---------------------------------------------------------------------------
# 3.3  State Extraction from institute text
# ---------------------------------------------------------------------------

# Ordered from longer/more specific to shorter to avoid false positives
INDIA_STATES: list[str] = [
    "Andaman and Nicobar Islands",
    "Arunachal Pradesh",
    "Andhra Pradesh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Dadra and Nagar Haveli",
    "Daman and Diu",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jammu & Kashmir",
    "Madhya Pradesh",
    "Uttar Pradesh",
    "Uttarakhand",
    "Uttaranchal",
    "West Bengal",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Chandigarh",
    "Delhi",
    "New Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Orissa",
    "Punjab",
    "Puducherry",
    "Pondicherry",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Tamilnadu",
    "Telangana",
    "Tripura",
]

# Canonical mappings for alternate spellings
_STATE_CANONICAL: dict[str, str] = {
    "New Delhi": "Delhi",
    "Jammu & Kashmir": "Jammu and Kashmir",
    "Uttaranchal": "Uttarakhand",
    "Orissa": "Odisha",
    "Tamilnadu": "Tamil Nadu",
    "Pondicherry": "Puducherry",
    "Dadra and Nagar Haveli and Daman and Diu": "Dadra and Nagar Haveli and Daman and Diu",
    "Daman and Diu": "Dadra and Nagar Haveli and Daman and Diu",
    "Dadra and Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
}

# Pincode prefix → state (6-digit Indian pincodes)
_PINCODE_STATE: dict[str, str] = {
    "11": "Delhi",
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
    "73": "West Bengal",
    "74": "West Bengal",
    "75": "Odisha", "76": "Odisha", "77": "Odisha",
    "78": "Assam",
    "79": "Assam",
    "80": "Bihar", "81": "Bihar", "82": "Bihar", "83": "Bihar",
    "84": "Bihar", "85": "Bihar",
    "82": "Jharkhand", "83": "Jharkhand",
    "90": "Rajasthan",
    "110": "Delhi",
}


def extract_state_from_institute(institute_raw: Optional[str]) -> Optional[str]:
    """
    Attempt to extract state from institute text.
    Strategy:
      1. Substring match against India state list (longest first)
      2. Pincode inference (6-digit number in text)
      3. Return None if not found
    """
    if not institute_raw:
        return None

    text = institute_raw.strip()

    # 1. Substring match (case-insensitive)
    text_upper = text.upper()
    for state in INDIA_STATES:
        if state.upper() in text_upper:
            return _STATE_CANONICAL.get(state, state)

    # 2. Pincode inference
    pincodes = re.findall(r'\b(\d{6})\b', text)
    for pin in pincodes:
        prefix2 = pin[:2]
        prefix3 = pin[:3]
        if prefix3 in _PINCODE_STATE:
            return _PINCODE_STATE[prefix3]
        if prefix2 in _PINCODE_STATE:
            return _PINCODE_STATE[prefix2]

    return None


def clean_institute_name(institute_raw: Optional[str]) -> Optional[str]:
    """
    Extract the human-readable institute name from the raw text.
    Raw text often contains: name + address + city + state + pincode + email/phone.
    Strategy: take everything before the first comma or newline after the main name.
    """
    if not institute_raw:
        return None

    text = institute_raw.strip()

    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)
    # Remove phone numbers
    text = re.sub(r'[\+\d][\d\s\-\(\)]{7,}', '', text)
    # Remove pincodes (6-digit standalone numbers)
    text = re.sub(r'\b\d{6}\b', '', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Split on comma: take first meaningful segment as the institute name
    parts = [p.strip() for p in re.split(r',', text) if p.strip()]
    if parts:
        # First part is usually the institute name
        name = parts[0]
        # Remove trailing punctuation
        name = name.rstrip('.,;:')
        return name if len(name) > 3 else text

    return text


# ---------------------------------------------------------------------------
# 3.4  Course Normalization
# ---------------------------------------------------------------------------

# Degree prefix normalization patterns: (pattern, replacement)
_DEGREE_PATTERNS: list[Tuple[str, str]] = [
    (r'M\.?C\.?H\.?', 'MCH'),
    (r'D\.?N\.?B\.?', 'DNB'),
    (r'D\.?M\.?', 'DM'),
    (r'M\.?D\.?', 'MD'),
    (r'M\.?S\.?', 'MS'),
    (r'M\.?B\.?B\.?S\.?', 'MBBS'),
    (r'M\.?Sc\.?', 'MSC'),
    (r'B\.?Sc\.?', 'BSC'),
    (r'DIPLOMA\s+IN', 'DIPLOMA'),
    (r'DIP\.?\s+IN', 'DIPLOMA'),
    (r'DIP\.?', 'DIPLOMA'),
]

# Degree detection (for ref_course split)
_KNOWN_DEGREES = ['MCH', 'DNB', 'DM', 'MD', 'MS', 'MBBS', 'MSC', 'BSC', 'DIPLOMA']


def normalize_course(raw: Optional[str]) -> str:
    """
    Normalise a course string to canonical form: "<DEGREE> <SPECIALTY>"
    e.g. "M.D. (General Medicine)" → "MD GENERAL MEDICINE"
    """
    if not raw:
        return ""

    # 1. Unicode → ASCII
    text = unicodedata.normalize('NFKD', raw)
    text = text.encode('ascii', 'ignore').decode('ascii')

    # 2. Uppercase
    text = text.upper()

    # 3. Remove parentheses (keep content)
    text = re.sub(r'[()]', ' ', text)
    text = re.sub(r'[\[\]]', ' ', text)

    # 4. Normalize degree prefixes (longest first to avoid partial matches)
    for pattern, replacement in _DEGREE_PATTERNS:
        text = re.sub(r'\b' + pattern + r'\b', replacement, text)

    # 5. Normalize hyphens and slashes to space
    text = re.sub(r'\s*[-–—/]\s*', ' ', text)

    # 6. Remove stray punctuation
    text = re.sub(r'[.,;:!?]', ' ', text)

    # 7. Collapse whitespace
    text = ' '.join(text.split())

    return text


def split_course_degree_specialty(course_norm: str) -> Tuple[Optional[str], Optional[str]]:
    """Split 'MD GENERAL MEDICINE' → ('MD', 'GENERAL MEDICINE')."""
    if not course_norm:
        return None, None
    for deg in _KNOWN_DEGREES:
        if course_norm.startswith(deg + ' '):
            return deg, course_norm[len(deg):].strip()
        if course_norm == deg:
            return deg, None
    return None, course_norm
