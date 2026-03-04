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
    "AFMS", "AFMS-DNB", "DNB Post MBBS", "MNG", "NBE Diploma", "NRI",
}

_QUOTA_ALIAS: dict[str, str] = {
    # AIQ (All India Quota)
    "AIQ": "AIQ",
    "AI": "AIQ",
    "A.I.": "AIQ",
    "A.I.Q.": "AIQ",
    "ALL INDIA": "AIQ",
    # AMU (Aligarh Muslim University)
    "AMU": "AMU",
    "A.M.U.": "AMU",
    "AM": "AMU",
    # BHU (Banaras Hindu University)
    "BHU": "BHU",
    "B.H.U.": "BHU",
    "BH": "BHU",
    # DU (Delhi University)
    "DU": "DU",
    "D.U.": "DU",
    "DELHI UNIVERSITY": "DU",
    # IP (IP University, Delhi)
    "IP": "IP",
    "I.P.": "IP",
    "IPCL": "IP",
    # JM (Jamia Millia Islamia)
    "JM": "JM",
    "J.M.": "JM",
    "JAMIA": "JM",
    # MM (Maulana Azad / Muslim Minority)
    "MM": "MM",
    "M.M.": "MM",
    # AFMS (Armed Forces Medical Services)
    "AFMS": "AFMS",
    "A.F.M.S.": "AFMS",
    "ARMED FORCES": "AFMS",
    # AFMS-DNB
    "AFMS-DNB": "AFMS-DNB",
    "AFMSDNB": "AFMS-DNB",
    # DNB Post MBBS
    "DNB POST MBBS": "DNB Post MBBS",
    "DNB-POST MBBS": "DNB Post MBBS",
    "AD": "DNB Post MBBS",
    "DNB": "DNB Post MBBS",
    # MNG (Management quota)
    "MNG": "MNG",
    "MANAGEMENT": "MNG",
    "MGT": "MNG",
    "PS": "MNG",
    # NBE Diploma
    "NBE DIPLOMA": "NBE Diploma",
    "NBE-DIPLOMA": "NBE Diploma",
    "DIPLOMA": "NBE Diploma",
    # NRI
    "NRI": "NRI",
    "N.R.I.": "NRI",
    "NR": "NRI",
}


def normalize_quota(raw: Optional[str]) -> Tuple[str, bool]:
    """Returns (quota_norm, is_known)."""
    if not raw:
        return "UNKNOWN", False
    key = raw.strip().upper().replace(" ", " ").strip()
    # Try direct lookup
    norm = _QUOTA_ALIAS.get(key)
    if norm:
        return norm, True
    # Try without spaces/hyphens
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
    "EWS-PWD": "EWS-PwD",
    "EWS-PH": "EWS-PwD",
    "EWS-PwD": "EWS-PwD",
    "OBC-PWD": "OBC-PwD",
    "OBC-PH": "OBC-PwD",
    "OBC-PwD": "OBC-PwD",
    "SC-PWD": "SC-PwD",
    "SC-PH": "SC-PwD",
    "SC-PwD": "SC-PwD",
    "ST-PWD": "ST-PwD",
    "ST-PH": "ST-PwD",
    "ST-PwD": "ST-PwD",
    # AFMS
    "AFMS-PRIORITY III": "AFMS-Priority III",
    "AFMS-PRIORITY-III": "AFMS-Priority III",
    "AFMS-P3": "AFMS-Priority III",
    "AFMS PRIORITY III": "AFMS-Priority III",
    "AFMS-Priority III": "AFMS-Priority III",
    "AFMS-PRIORITY IV": "AFMS-Priority IV",
    "AFMS-PRIORITY-IV": "AFMS-Priority IV",
    "AFMS-P4": "AFMS-Priority IV",
    "AFMS PRIORITY IV": "AFMS-Priority IV",
    "AFMS-Priority IV": "AFMS-Priority IV",
}


def normalize_category(raw: Optional[str]) -> Tuple[str, bool]:
    """Returns (category_norm, is_known)."""
    if not raw:
        return "UNKNOWN", False
    key = raw.strip()
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
