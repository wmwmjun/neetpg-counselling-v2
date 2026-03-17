#!/usr/bin/env python3
"""
Comprehensive NEET-PG 2025 Round-1 demo seed.
Targets ~26,000 allotment rows → ~14,000 closing-rank groups.

Run from backend/:
    python -m scripts.seed            # seed (skip if already seeded)
    python -m scripts.seed --clear    # clear and reseed
"""
import random, sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app import models  # noqa
from app.models import Allotment, RefCourse as RC, IngestionProgress
from ingestion.normalizers import normalize_course, split_course_degree_specialty, classify_course_type

random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# ALL COURSES (matching real NEET-PG 2025 schedule)
# ─────────────────────────────────────────────────────────────────────────────
ALL_COURSES = [
    # Diploma
    "Diploma in Anaesthesia",
    "Diploma in Anaesthesia-NBE",
    "Diploma in Child Health",
    "Diploma in Child Health-NBE",
    "Diploma in Clinical Pathology",
    "Diploma in Dermatology, Venereology and Leprosy",
    "Diploma in Diabetology",
    "Diploma in Emergency Medicine-NBE",
    "Diploma in Family Medicine-NBE",
    "Diploma in Forensic Medicine",
    "Diploma in Health Administration",
    "Diploma in Immuno-Haematology and Blood Transfusion",
    "Diploma in Microbiology",
    "Diploma in Obstetrics & Gynaecology",
    "Diploma in Obstetrics & Gynaecology-NBE",
    "Diploma in Ophthalmology",
    "Diploma in Ophthalmology-NBE",
    "Diploma in Orthopaedics",
    "Diploma in Oto-Rhino-Laryngology",
    "Diploma in Oto-Rhino-Laryngology-NBE",
    "Diploma in Physical Medicine & Rehabilitation",
    "Diploma in Psychological Medicine",
    "Diploma in Public Health",
    "Diploma in Radiation Medicine",
    "Diploma in Radio-Diagnosis",
    "Diploma in Radio-Diagnosis-NBE",
    "Diploma in Radio Therapy",
    "Diploma in Sports Medicine",
    "Diploma in Tuberculosis & Chest Diseases",
    "Diploma in Tuberculosis & Chest Diseases-NBE",
    # DNB
    "DNB Anaesthesiology",
    "DNB Anatomy",
    "DNB Biochemistry",
    "DNB Cardio Thoracic Surgery (6 years)",
    "DNB Dermatology & Venereology",
    "DNB Emergency Medicine",
    "DNB ENT",
    "DNB Family Medicine",
    "DNB Forensic Medicine",
    "DNB General Medicine",
    "DNB General Surgery",
    "DNB Geriatric Medicine",
    "DNB Health Administration including Hospital Administration",
    "DNB Immuno Hematology & Transfusion Medicine",
    "DNB Microbiology",
    "DNB Neuro Surgery (6 years)",
    "DNB Nuclear Medicine",
    "DNB Obstetrics & Gynaecology",
    "DNB Ophthalmology",
    "DNB Orthopedics Surgery",
    "DNB Paediatrics",
    "DNB Paediatric Surgery (6 years)",
    "DNB Palliative Medicine",
    "DNB Pathology",
    "DNB Pharmacology",
    "DNB Physical Medicine & Rehabilitation",
    "DNB Physiology",
    "DNB Plastic Surgery (6 years)",
    "DNB Psychiatry",
    "DNB Radio Diagnosis",
    "DNB Radio Therapy",
    "DNB Respiratory Diseases",
    "DNB Social & Preventive Medicine",
    # MPH / Super Specialty
    "Master of Public Health (Epidemiology)",
    "MCh Neurosurgery (6 years)",
    # MD
    "MD Anaesthesiology",
    "MD Anatomy",
    "MD Aviation Medicine/Aerospace Medicine",
    "MD Bio-Chemistry",
    "MD Community Health Administration",
    "MD Dermatology, Venereology & Leprosy",
    "MD Emergency Medicine",
    "MD Family Medicine",
    "MD Forensic Medicine",
    "MD General Medicine",
    "MD Geriatrics",
    "MD Hospital Administration",
    "MD Immuno Haematology & Blood Transfusion",
    "MD Lab Medicine",
    "MD Microbiology",
    "MD Nuclear Medicine",
    "MD Paediatrics",
    "MD Palliative Medicine",
    "MD Pathology",
    "MD Pharmacology",
    "MD Physical Medicine & Rehabilitation",
    "MD Physiology",
    "MD Psychiatry",
    "MD Radiation Oncology",
    "MD Radio Diagnosis",
    "MD Social & Preventive Medicine",
    "MD Sports Medicine",
    "MD Tropical Medicine",
    "MD Tuberculosis & Respiratory Diseases",
    # MS
    "MS ENT",
    "MS General Surgery",
    "MS Obstetrics & Gynaecology",
    "MS Ophthalmology",
    "MS Orthopaedics",
    "MS Traumatology and Surgery",
]

# Course → desirability score (lower = more competitive; affects base rank)
_DESIRABILITY: dict[str, float] = {
    "MD Dermatology, Venereology & Leprosy": 0.3,
    "MD Radio Diagnosis": 0.5,
    "MS Orthopaedics": 0.7,
    "MD General Medicine": 0.8,
    "MS General Surgery": 0.9,
    "MD Paediatrics": 1.0,
    "MS Obstetrics & Gynaecology": 1.1,
    "MS Ophthalmology": 1.2,
    "MS ENT": 1.4,
    "MD Psychiatry": 1.8,
    "MD Anaesthesiology": 1.9,
    "MD Emergency Medicine": 2.0,
    "MD Radiation Oncology": 2.2,
    "MD Nuclear Medicine": 2.5,
    "MD Pathology": 2.8,
    "MD Microbiology": 3.0,
    "MD Pharmacology": 3.2,
    "MD Anatomy": 4.0,
    "MD Physiology": 4.2,
    "MD Bio-Chemistry": 4.5,
    "MD Forensic Medicine": 4.0,
    "MD Social & Preventive Medicine": 3.5,
    "MD Community Health Administration": 3.8,
    "MD Hospital Administration": 3.5,
    "MD Family Medicine": 3.0,
    "DNB General Medicine": 1.3,
    "DNB General Surgery": 1.5,
    "DNB Radio Diagnosis": 0.7,
    "DNB Dermatology & Venereology": 0.5,
    "DNB Anaesthesiology": 2.2,
    "DNB Paediatrics": 1.4,
    "DNB Obstetrics & Gynaecology": 1.5,
    "DNB Ophthalmology": 1.6,
    "DNB ENT": 1.8,
    "DNB Pathology": 3.2,
    "DNB Psychiatry": 2.5,
}

def desirability(course_raw: str) -> float:
    for k, v in _DESIRABILITY.items():
        if k in course_raw:
            return v
    if course_raw.startswith("Diploma"):
        return 4.0
    if course_raw.startswith("DNB"):
        return 2.5
    if "6 years" in course_raw:
        return 1.5
    return 2.0

# ─────────────────────────────────────────────────────────────────────────────
# INSTITUTES by state
# (name, state, tier, quotas, course_profile)
# tier: 1=AIIMS/central, 2=major GMC/central univ, 3=state GMC, 4=DNB hosp, 5=diploma
# course_profile: 'full','clinical','md_ms','dnb','diploma','basic'
# ─────────────────────────────────────────────────────────────────────────────

INSTITUTES = [
    # ── Delhi ──
    ("AIIMS, New Delhi", "Delhi", 1, ["AIQ", "AFMS"], "full"),
    ("ABVIMS & Dr. Ram Manohar Lohia Hospital, New Delhi", "Delhi", 2, ["AIQ", "IP"], "clinical"),
    ("VMMC & Safdarjung Hospital, New Delhi", "Delhi", 2, ["AIQ", "IP"], "full"),
    ("Lady Hardinge Medical College, New Delhi", "Delhi", 2, ["AIQ", "DU"], "clinical"),
    ("Maulana Azad Medical College, New Delhi", "Delhi", 2, ["AIQ", "DU", "MM"], "full"),
    ("University College of Medical Sciences, Delhi", "Delhi", 2, ["AIQ", "DU"], "full"),
    ("Army College of Medical Sciences, New Delhi", "Delhi", 2, ["AFMS"], "clinical"),
    ("Jamia Hamdard (Hamdard Institute of Med Sci), New Delhi", "Delhi", 2, ["AIQ", "JM"], "clinical"),
    ("Sir Ganga Ram Hospital, New Delhi", "Delhi", 4, ["DNB Post MBBS"], "dnb"),
    ("Apollo Hospitals, New Delhi", "Delhi", 4, ["DNB Post MBBS", "MNG"], "dnb"),
    ("Indraprastha Apollo Hospital, New Delhi", "Delhi", 4, ["DNB Post MBBS"], "dnb"),
    ("Max Super Speciality Hospital, Saket, New Delhi", "Delhi", 4, ["DNB Post MBBS"], "dnb"),
    ("Holy Family Hospital, New Delhi", "Delhi", 4, ["DNB Post MBBS"], "dnb"),
    ("BLK-Max Super Speciality Hospital, New Delhi", "Delhi", 4, ["DNB Post MBBS"], "dnb"),
    ("Fortis Hospital, Vasant Kunj, New Delhi", "Delhi", 4, ["DNB Post MBBS"], "dnb"),

    # ── Maharashtra ──
    ("AIIMS, Nagpur", "Maharashtra", 1, ["AIQ"], "full"),
    ("Grant Medical College & Sir J.J. Group of Hospitals, Mumbai", "Maharashtra", 2, ["AIQ"], "full"),
    ("Seth G.S. Medical College & KEM Hospital, Mumbai", "Maharashtra", 2, ["AIQ"], "full"),
    ("Topiwala National Medical College, Mumbai", "Maharashtra", 2, ["AIQ"], "clinical"),
    ("B.J. Government Medical College, Pune", "Maharashtra", 2, ["AIQ"], "full"),
    ("Government Medical College, Aurangabad", "Maharashtra", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Nagpur", "Maharashtra", 3, ["AIQ"], "clinical"),
    ("Rajiv Gandhi Medical College, Thane", "Maharashtra", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Latur", "Maharashtra", 3, ["AIQ"], "basic"),
    ("Government Medical College, Nanded", "Maharashtra", 3, ["AIQ"], "basic"),
    ("Kokilaben Dhirubhai Ambani Hospital, Mumbai", "Maharashtra", 4, ["DNB Post MBBS", "MNG"], "dnb"),
    ("Lilavati Hospital, Mumbai", "Maharashtra", 4, ["DNB Post MBBS"], "dnb"),
    ("Bombay Hospital, Mumbai", "Maharashtra", 4, ["DNB Post MBBS"], "dnb"),
    ("Ruby Hall Clinic, Pune", "Maharashtra", 4, ["DNB Post MBBS"], "dnb"),
    ("Deenanath Mangeshkar Hospital, Pune", "Maharashtra", 4, ["DNB Post MBBS"], "dnb"),

    # ── Uttar Pradesh ──
    ("AIIMS, Gorakhpur", "Uttar Pradesh", 1, ["AIQ"], "full"),
    ("Institute of Medical Sciences, BHU, Varanasi", "Uttar Pradesh", 2, ["AIQ", "BHU"], "full"),
    ("Jawaharlal Nehru Medical College, AMU, Aligarh", "Uttar Pradesh", 2, ["AIQ", "AMU"], "full"),
    ("King George's Medical University, Lucknow", "Uttar Pradesh", 2, ["AIQ"], "full"),
    ("Moti Lal Nehru Medical College, Prayagraj", "Uttar Pradesh", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Kanpur", "Uttar Pradesh", 3, ["AIQ"], "clinical"),
    ("S.N. Medical College, Agra", "Uttar Pradesh", 3, ["AIQ"], "clinical"),
    ("B.R.D. Medical College, Gorakhpur", "Uttar Pradesh", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Jhansi", "Uttar Pradesh", 3, ["AIQ"], "clinical"),
    ("S.P.M. Civil Hospital, Meerut", "Uttar Pradesh", 3, ["AIQ"], "basic"),
    ("Government Medical College, Azamgarh", "Uttar Pradesh", 3, ["AIQ"], "basic"),
    ("Government Medical College, Fatehpur", "Uttar Pradesh", 3, ["AIQ"], "basic"),
    ("Rama Medical College, Hapur", "Uttar Pradesh", 4, ["DNB Post MBBS", "NRI"], "dnb"),
    ("Era's Lucknow Medical College, Lucknow", "Uttar Pradesh", 4, ["DNB Post MBBS", "NRI"], "dnb"),
    ("Sahara Hospital, Lucknow", "Uttar Pradesh", 4, ["DNB Post MBBS"], "dnb"),

    # ── Tamil Nadu ──
    ("AIIMS, Madurai", "Tamil Nadu", 1, ["AIQ"], "full"),
    ("Jawaharlal Institute of Postgraduate Medical Education & Research (JIPMER), Puducherry", "Puducherry", 1, ["AIQ"], "full"),
    ("Madras Medical College, Chennai", "Tamil Nadu", 2, ["AIQ"], "full"),
    ("Stanley Medical College, Chennai", "Tamil Nadu", 2, ["AIQ"], "full"),
    ("Kilpauk Medical College, Chennai", "Tamil Nadu", 2, ["AIQ"], "clinical"),
    ("Coimbatore Medical College, Coimbatore", "Tamil Nadu", 3, ["AIQ"], "clinical"),
    ("Tirunelveli Medical College, Tirunelveli", "Tamil Nadu", 3, ["AIQ"], "clinical"),
    ("Government Rajaji Hospital, Madurai", "Tamil Nadu", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Salem", "Tamil Nadu", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Vellore", "Tamil Nadu", 3, ["AIQ"], "basic"),
    ("Thanjavur Medical College, Thanjavur", "Tamil Nadu", 3, ["AIQ"], "clinical"),
    ("Christian Medical College, Vellore", "Tamil Nadu", 2, ["AIQ", "DNB Post MBBS"], "full"),
    ("Apollo Hospital, Chennai", "Tamil Nadu", 4, ["DNB Post MBBS", "MNG"], "dnb"),
    ("MIOT International, Chennai", "Tamil Nadu", 4, ["DNB Post MBBS"], "dnb"),

    # ── Karnataka ──
    ("AIIMS, Mangalagiri", "Andhra Pradesh", 1, ["AIQ"], "full"),  # actually Mangalagiri is AP but listing here
    ("NIMHANS, Bengaluru", "Karnataka", 1, ["AIQ"], "clinical"),
    ("Bangalore Medical College & Research Institute, Bengaluru", "Karnataka", 2, ["AIQ"], "full"),
    ("MS Ramaiah Medical College, Bengaluru", "Karnataka", 3, ["AIQ", "NRI", "MNG"], "clinical"),
    ("Kasturba Medical College, Manipal", "Karnataka", 2, ["AIQ", "NRI"], "full"),
    ("Kasturba Medical College, Mangalore", "Karnataka", 2, ["AIQ", "NRI"], "full"),
    ("JSS Medical College, Mysuru", "Karnataka", 3, ["AIQ", "NRI"], "clinical"),
    ("Mysore Medical College & Research Institute, Mysuru", "Karnataka", 3, ["AIQ"], "clinical"),
    ("Kempegowda Institute of Medical Sciences, Bengaluru", "Karnataka", 3, ["AIQ", "NRI"], "clinical"),
    ("Hassan Institute of Medical Sciences, Hassan", "Karnataka", 3, ["AIQ"], "basic"),
    ("St John's Medical College, Bengaluru", "Karnataka", 3, ["AIQ", "DNB Post MBBS"], "clinical"),

    # ── Kerala ──
    ("AIIMS, Thiruvananthapuram", "Kerala", 1, ["AIQ"], "full"),
    ("Government Medical College, Thiruvananthapuram", "Kerala", 2, ["AIQ"], "full"),
    ("Government Medical College, Kozhikode", "Kerala", 2, ["AIQ"], "full"),
    ("Government Medical College, Kottayam", "Kerala", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Thrissur", "Kerala", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Ernakulam", "Kerala", 3, ["AIQ"], "clinical"),
    ("Amrita Institute of Medical Sciences, Kochi", "Kerala", 3, ["AIQ", "NRI", "MNG"], "clinical"),
    ("Pushpagiri Medical College, Thiruvalla", "Kerala", 3, ["AIQ", "NRI"], "clinical"),
    ("Jubilee Mission Medical College, Thrissur", "Kerala", 4, ["DNB Post MBBS", "NRI"], "dnb"),

    # ── Andhra Pradesh ──
    ("Government Medical College, Guntur", "Andhra Pradesh", 2, ["AIQ"], "clinical"),
    ("Andhra Medical College, Visakhapatnam", "Andhra Pradesh", 2, ["AIQ"], "full"),
    ("Rangaraya Medical College, Kakinada", "Andhra Pradesh", 3, ["AIQ"], "clinical"),
    ("Kurnool Medical College, Kurnool", "Andhra Pradesh", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Anantapur", "Andhra Pradesh", 3, ["AIQ"], "basic"),
    ("S.V. Medical College, Tirupati", "Andhra Pradesh", 3, ["AIQ"], "clinical"),

    # ── Telangana ──
    ("AIIMS, Bibinagar", "Telangana", 1, ["AIQ"], "full"),
    ("Osmania Medical College, Hyderabad", "Telangana", 2, ["AIQ"], "full"),
    ("Gandh Medical College, Secunderabad", "Telangana", 2, ["AIQ"], "full"),
    ("Kakatiya Medical College, Warangal", "Telangana", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Nizamabad", "Telangana", 3, ["AIQ"], "basic"),
    ("Deccan College of Medical Sciences, Hyderabad", "Telangana", 3, ["AIQ", "NRI"], "clinical"),
    ("Yashoda Hospitals, Hyderabad", "Telangana", 4, ["DNB Post MBBS"], "dnb"),

    # ── Rajasthan ──
    ("AIIMS, Jodhpur", "Rajasthan", 1, ["AIQ"], "full"),
    ("SMS Medical College, Jaipur", "Rajasthan", 2, ["AIQ"], "full"),
    ("Dr. S.N. Medical College, Jodhpur", "Rajasthan", 3, ["AIQ"], "clinical"),
    ("JLN Medical College, Ajmer", "Rajasthan", 3, ["AIQ"], "clinical"),
    ("RNT Medical College, Udaipur", "Rajasthan", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Kota", "Rajasthan", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Bharatpur", "Rajasthan", 3, ["AIQ"], "basic"),
    ("Santokba Durlabhji Memorial Hospital, Jaipur", "Rajasthan", 4, ["DNB Post MBBS"], "dnb"),

    # ── Madhya Pradesh ──
    ("AIIMS, Bhopal", "Madhya Pradesh", 1, ["AIQ"], "full"),
    ("Gandhi Medical College, Bhopal", "Madhya Pradesh", 2, ["AIQ"], "full"),
    ("MGM Medical College, Indore", "Madhya Pradesh", 2, ["AIQ"], "full"),
    ("G.R. Medical College, Gwalior", "Madhya Pradesh", 3, ["AIQ"], "clinical"),
    ("S.S. Medical College, Rewa", "Madhya Pradesh", 3, ["AIQ"], "clinical"),
    ("Bundelkhand Medical College, Sagar", "Madhya Pradesh", 3, ["AIQ"], "clinical"),
    ("Chirayu Medical College, Bhopal", "Madhya Pradesh", 3, ["AIQ", "NRI"], "clinical"),
    ("Choithram Hospital & Research Centre, Indore", "Madhya Pradesh", 4, ["DNB Post MBBS"], "dnb"),

    # ── Gujarat ──
    ("AIIMS, Rajkot", "Gujarat", 1, ["AIQ"], "full"),
    ("B.J. Medical College, Ahmedabad", "Gujarat", 2, ["AIQ"], "full"),
    ("Smt. NHL Municipal Medical College, Ahmedabad", "Gujarat", 2, ["AIQ"], "clinical"),
    ("Government Medical College, Surat", "Gujarat", 3, ["AIQ"], "clinical"),
    ("M.P. Shah Government Medical College, Jamnagar", "Gujarat", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Rajkot", "Gujarat", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Baroda", "Gujarat", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Bhavnagar", "Gujarat", 3, ["AIQ"], "basic"),
    ("Sterling Hospital, Ahmedabad", "Gujarat", 4, ["DNB Post MBBS"], "dnb"),
    ("HCG Cancer Centre, Ahmedabad", "Gujarat", 4, ["DNB Post MBBS"], "dnb"),

    # ── Punjab ──
    ("AIIMS, Bathinda", "Punjab", 1, ["AIQ"], "full"),
    ("Government Medical College, Amritsar", "Punjab", 2, ["AIQ"], "full"),
    ("Government Medical College, Patiala", "Punjab", 2, ["AIQ"], "clinical"),
    ("Dayanand Medical College, Ludhiana", "Punjab", 3, ["AIQ", "NRI"], "clinical"),
    ("Sri Guru Ram Dass Institute of Medical Sciences, Amritsar", "Punjab", 3, ["AIQ", "NRI"], "clinical"),
    ("Christian Medical College, Ludhiana", "Punjab", 3, ["AIQ", "DNB Post MBBS"], "clinical"),

    # ── Haryana ──
    ("AIIMS, Rewari", "Haryana", 1, ["AIQ"], "full"),
    ("Pt. BD Sharma PGIMS, Rohtak", "Haryana", 2, ["AIQ"], "full"),
    ("ESIC Medical College, Faridabad", "Haryana", 3, ["AIQ"], "clinical"),
    ("Kalpana Chawla Government Medical College, Karnal", "Haryana", 3, ["AIQ"], "clinical"),
    ("Maharishi Markandeshwar Institute of Med Sci, Mullana", "Haryana", 3, ["AIQ", "NRI"], "clinical"),
    ("BPS Government Medical College, Sonepat", "Haryana", 3, ["AIQ"], "basic"),

    # ── Chandigarh ──
    ("PGIMER, Chandigarh", "Chandigarh", 1, ["AIQ"], "full"),
    ("Government Medical College, Chandigarh", "Chandigarh", 2, ["AIQ"], "full"),

    # ── West Bengal ──
    ("AIIMS, Kalyani", "West Bengal", 1, ["AIQ"], "full"),
    ("IPGMER & SSKM Hospital, Kolkata", "West Bengal", 2, ["AIQ"], "full"),
    ("Medical College, Kolkata", "West Bengal", 2, ["AIQ"], "full"),
    ("NRS Medical College, Kolkata", "West Bengal", 2, ["AIQ"], "clinical"),
    ("R.G. Kar Medical College, Kolkata", "West Bengal", 3, ["AIQ"], "clinical"),
    ("Calcutta National Medical College, Kolkata", "West Bengal", 3, ["AIQ"], "clinical"),
    ("North Bengal Medical College, Darjeeling", "West Bengal", 3, ["AIQ"], "clinical"),
    ("Bankura Sammilani Medical College, Bankura", "West Bengal", 3, ["AIQ"], "basic"),
    ("Burdwan Medical College, Burdwan", "West Bengal", 3, ["AIQ"], "clinical"),
    ("AMRI Hospitals, Kolkata", "West Bengal", 4, ["DNB Post MBBS"], "dnb"),

    # ── Odisha ──
    ("AIIMS, Bhubaneswar", "Odisha", 1, ["AIQ"], "full"),
    ("SCB Medical College, Cuttack", "Odisha", 2, ["AIQ"], "full"),
    ("MKCG Medical College, Berhampur", "Odisha", 3, ["AIQ"], "clinical"),
    ("VSS Medical College, Burla", "Odisha", 3, ["AIQ"], "clinical"),
    ("Hi-Tech Medical College, Bhubaneswar", "Odisha", 4, ["DNB Post MBBS", "NRI"], "dnb"),

    # ── Bihar ──
    ("AIIMS, Patna", "Bihar", 1, ["AIQ"], "full"),
    ("Patna Medical College, Patna", "Bihar", 2, ["AIQ"], "full"),
    ("Darbhanga Medical College, Darbhanga", "Bihar", 3, ["AIQ"], "clinical"),
    ("JLNMC & Hospital, Bhagalpur", "Bihar", 3, ["AIQ"], "clinical"),
    ("Nalanda Medical College, Patna", "Bihar", 3, ["AIQ"], "clinical"),
    ("Sri Krishna Medical College, Muzaffarpur", "Bihar", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Bettiah", "Bihar", 3, ["AIQ"], "basic"),
    ("Government Medical College, Gaya", "Bihar", 3, ["AIQ"], "basic"),

    # ── Jharkhand ──
    ("AIIMS, Deoghar", "Jharkhand", 1, ["AIQ"], "full"),
    ("Rajendra Institute of Medical Sciences, Ranchi", "Jharkhand", 2, ["AIQ"], "full"),
    ("Patliputra Medical College, Dhanbad", "Jharkhand", 3, ["AIQ"], "clinical"),
    ("MGM Medical College, Jamshedpur", "Jharkhand", 3, ["AIQ", "NRI"], "clinical"),

    # ── Chhattisgarh ──
    ("AIIMS, Raipur", "Chhattisgarh", 1, ["AIQ"], "full"),
    ("Pandit JNM Medical College, Raipur", "Chhattisgarh", 2, ["AIQ"], "full"),
    ("Government Medical College, Rajnandgaon", "Chhattisgarh", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Jagdalpur", "Chhattisgarh", 3, ["AIQ"], "basic"),

    # ── Himachal Pradesh ──
    ("AIIMS, Bilaspur", "Himachal Pradesh", 1, ["AIQ"], "full"),
    ("Indira Gandhi Medical College, Shimla", "Himachal Pradesh", 2, ["AIQ"], "full"),
    ("Dr. Rajendra Prasad Government Medical College, Kangra", "Himachal Pradesh", 3, ["AIQ"], "clinical"),

    # ── Uttarakhand ──
    ("AIIMS, Rishikesh", "Uttarakhand", 1, ["AIQ"], "full"),
    ("Government Medical College, Haldwani", "Uttarakhand", 2, ["AIQ"], "clinical"),
    ("Himalayan Institute of Medical Sciences, Dehradun", "Uttarakhand", 3, ["AIQ", "NRI"], "clinical"),

    # ── Jammu and Kashmir ──
    ("AIIMS, Jammu", "Jammu and Kashmir", 1, ["AIQ"], "full"),
    ("Government Medical College, Jammu", "Jammu and Kashmir", 2, ["AIQ"], "full"),
    ("Government Medical College, Srinagar", "Jammu and Kashmir", 2, ["AIQ"], "full"),
    ("SKIMS, Srinagar", "Jammu and Kashmir", 2, ["AIQ"], "clinical"),

    # ── Assam ──
    ("AIIMS, Guwahati", "Assam", 1, ["AIQ"], "full"),
    ("Gauhati Medical College, Guwahati", "Assam", 2, ["AIQ"], "full"),
    ("Silchar Medical College, Silchar", "Assam", 3, ["AIQ"], "clinical"),
    ("Jorhat Medical College, Jorhat", "Assam", 3, ["AIQ"], "clinical"),

    # ── Arunachal Pradesh ──
    ("TRIHMS (Tomo Riba Institute), Naharlagun", "Arunachal Pradesh", 3, ["AIQ"], "basic"),

    # ── Manipur ──
    ("AIIMS, Imphal", "Manipur", 1, ["AIQ"], "full"),
    ("Regional Institute of Medical Sciences, Imphal", "Manipur", 2, ["AIQ"], "clinical"),

    # ── Meghalaya ──
    ("NEIGRIHMS, Shillong", "Meghalaya", 1, ["AIQ"], "full"),
    ("Government Medical College, Shillong", "Meghalaya", 3, ["AIQ"], "clinical"),

    # ── Mizoram ──
    ("Zoram Medical College, Falkawn", "Mizoram", 3, ["AIQ"], "basic"),

    # ── Nagaland ──
    ("Government Medical College, Kohima", "Nagaland", 3, ["AIQ"], "basic"),

    # ── Tripura ──
    ("AGARTALA Government Medical College, Agartala", "Tripura", 3, ["AIQ"], "clinical"),
    ("Government Medical College, Dharmanagar", "Tripura", 3, ["AIQ"], "basic"),

    # ── Sikkim ──
    ("STNM Hospital, Gangtok", "Sikkim", 3, ["AIQ"], "basic"),

    # ── Ladakh ──
    ("SNM Hospital, Leh", "Ladakh", 3, ["AIQ"], "basic"),

    # ── Puducherry ──
    ("JIPMER, Karaikal", "Puducherry", 2, ["AIQ"], "clinical"),
    ("Sri Venkateshwaraa Medical College, Puducherry", "Puducherry", 3, ["AIQ", "NRI"], "clinical"),

    # ── Goa ──
    ("Goa Medical College, Panaji", "Goa", 2, ["AIQ"], "full"),
    ("Manipal College of Medical Sciences, North Goa", "Goa", 3, ["AIQ", "NRI"], "clinical"),

    # ── Andaman and Nicobar Islands ──
    ("Government Medical College & Hospital, Port Blair", "Andaman and Nicobar Islands", 3, ["AIQ"], "basic"),

    # ── AFMS hospitals (Delhi/country-wide) ──
    ("Army Hospital (Research & Referral), New Delhi", "Delhi", 2, ["AFMS", "AFMS-DNB"], "clinical"),
    ("Command Hospital (Southern Command), Pune", "Maharashtra", 2, ["AFMS", "AFMS-DNB"], "clinical"),
    ("Command Hospital (Western Command), Chandimandir", "Haryana", 2, ["AFMS", "AFMS-DNB"], "clinical"),
    ("Command Hospital (Eastern Command), Kolkata", "West Bengal", 2, ["AFMS", "AFMS-DNB"], "clinical"),
    ("Command Hospital (Central Command), Lucknow", "Uttar Pradesh", 2, ["AFMS", "AFMS-DNB"], "clinical"),
    ("Military Hospital, Chennai", "Tamil Nadu", 3, ["AFMS"], "basic"),

    # ── DNB standalone hospitals ──
    ("Medanta-The Medicity, Gurugram", "Haryana", 4, ["DNB Post MBBS"], "dnb"),
    ("Fortis Memorial Research Institute, Gurugram", "Haryana", 4, ["DNB Post MBBS"], "dnb"),
    ("Narayana Superspeciality Hospital, Gurugram", "Haryana", 4, ["DNB Post MBBS"], "dnb"),
    ("Jaypee Hospital, Noida", "Uttar Pradesh", 4, ["DNB Post MBBS", "MNG"], "dnb"),
    ("Fortis Escorts Heart Institute, New Delhi", "Delhi", 4, ["DNB Post MBBS"], "dnb"),
    ("Manipal Hospitals, Bengaluru", "Karnataka", 4, ["DNB Post MBBS", "MNG"], "dnb"),
    ("Narayana Health City, Bengaluru", "Karnataka", 4, ["DNB Post MBBS"], "dnb"),
    ("BGS Gleneagles Global Hospitals, Bengaluru", "Karnataka", 4, ["DNB Post MBBS"], "dnb"),
    ("Global Hospitals, Mumbai", "Maharashtra", 4, ["DNB Post MBBS"], "dnb"),
    ("Wockhardt Hospital, Mumbai", "Maharashtra", 4, ["DNB Post MBBS"], "dnb"),
    ("Breach Candy Hospital, Mumbai", "Maharashtra", 4, ["DNB Post MBBS"], "dnb"),
    ("Narayana Multispeciality Hospital, Kolkata", "West Bengal", 4, ["DNB Post MBBS"], "dnb"),
    ("Rabindranath Tagore International Institute, Kolkata", "West Bengal", 4, ["DNB Post MBBS"], "dnb"),
    ("Asian Institute of Gastroenterology, Hyderabad", "Telangana", 4, ["DNB Post MBBS"], "dnb"),
    ("Care Hospitals, Hyderabad", "Telangana", 4, ["DNB Post MBBS"], "dnb"),
    ("Sunshine Hospitals, Hyderabad", "Telangana", 4, ["DNB Post MBBS"], "dnb"),
    ("Kovai Medical Centre, Coimbatore", "Tamil Nadu", 4, ["DNB Post MBBS", "MNG"], "dnb"),
    ("PSG Hospitals, Coimbatore", "Tamil Nadu", 4, ["DNB Post MBBS"], "dnb"),
    ("Gem Hospital, Coimbatore", "Tamil Nadu", 4, ["DNB Post MBBS"], "dnb"),
    ("Amrita Hospital, Faridabad", "Haryana", 4, ["DNB Post MBBS", "NRI"], "dnb"),
    ("NMC Healthcare, Hyderabad", "Telangana", 4, ["DNB Post MBBS"], "dnb"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Course profiles → which courses are available at each profile type
# ─────────────────────────────────────────────────────────────────────────────
MD_CLINICAL = [
    "MD Anaesthesiology", "MD Dermatology, Venereology & Leprosy", "MD Emergency Medicine",
    "MD Family Medicine", "MD General Medicine", "MD Geriatrics", "MD Lab Medicine",
    "MD Nuclear Medicine", "MD Paediatrics", "MD Palliative Medicine", "MD Physical Medicine & Rehabilitation",
    "MD Psychiatry", "MD Radiation Oncology", "MD Radio Diagnosis", "MD Sports Medicine",
    "MD Tuberculosis & Respiratory Diseases", "MD Immuno Haematology & Blood Transfusion",
]
MS_CLINICAL = [
    "MS ENT", "MS General Surgery", "MS Obstetrics & Gynaecology",
    "MS Ophthalmology", "MS Orthopaedics", "MS Traumatology and Surgery",
]
MD_BASIC = [
    "MD Anatomy", "MD Bio-Chemistry", "MD Community Health Administration",
    "MD Forensic Medicine", "MD Hospital Administration", "MD Microbiology",
    "MD Pharmacology", "MD Physiology", "MD Social & Preventive Medicine", "MD Tropical Medicine",
]
DNB_COURSES = [
    "DNB Anaesthesiology", "DNB Dermatology & Venereology", "DNB Emergency Medicine",
    "DNB ENT", "DNB Family Medicine", "DNB General Medicine", "DNB General Surgery",
    "DNB Nuclear Medicine", "DNB Obstetrics & Gynaecology", "DNB Ophthalmology",
    "DNB Orthopedics Surgery", "DNB Paediatrics", "DNB Pathology", "DNB Pharmacology",
    "DNB Physical Medicine & Rehabilitation", "DNB Psychiatry", "DNB Radio Diagnosis",
    "DNB Radio Therapy", "DNB Respiratory Diseases",
]
DNB_SURGICAL = [
    "DNB Cardio Thoracic Surgery (6 years)", "DNB Neuro Surgery (6 years)",
    "DNB Paediatric Surgery (6 years)", "DNB Plastic Surgery (6 years)",
]
DIPLOMA_COURSES = [
    "Diploma in Anaesthesia", "Diploma in Child Health", "Diploma in Clinical Pathology",
    "Diploma in Dermatology, Venereology and Leprosy", "Diploma in Forensic Medicine",
    "Diploma in Obstetrics & Gynaecology", "Diploma in Ophthalmology", "Diploma in Orthopaedics",
    "Diploma in Oto-Rhino-Laryngology", "Diploma in Physical Medicine & Rehabilitation",
    "Diploma in Psychological Medicine", "Diploma in Radio-Diagnosis",
    "Diploma in Tuberculosis & Chest Diseases",
]
NBE_DIPLOMA = [
    "Diploma in Anaesthesia-NBE", "Diploma in Child Health-NBE", "Diploma in Emergency Medicine-NBE",
    "Diploma in Family Medicine-NBE", "Diploma in Obstetrics & Gynaecology-NBE",
    "Diploma in Ophthalmology-NBE", "Diploma in Oto-Rhino-Laryngology-NBE",
    "Diploma in Radio-Diagnosis-NBE", "Diploma in Tuberculosis & Chest Diseases-NBE",
]
SPECIAL_COURSES = [
    "Master of Public Health (Epidemiology)", "MCh Neurosurgery (6 years)",
    "MD Aviation Medicine/Aerospace Medicine",
]

PROFILE_COURSES: dict[str, list[str]] = {
    "full": MD_CLINICAL + MS_CLINICAL + MD_BASIC + DNB_COURSES[:8] + DNB_SURGICAL + DIPLOMA_COURSES + SPECIAL_COURSES,
    "clinical": MD_CLINICAL + MS_CLINICAL + DIPLOMA_COURSES[:8],
    "md_ms": MD_CLINICAL + MS_CLINICAL,
    "basic": MD_BASIC + MD_CLINICAL[:6] + MS_CLINICAL[:3] + DIPLOMA_COURSES[:6],
    "dnb": DNB_COURSES + DNB_SURGICAL + NBE_DIPLOMA,
    "diploma": DIPLOMA_COURSES + NBE_DIPLOMA,
}

# ─────────────────────────────────────────────────────────────────────────────
# Categories per quota
# ─────────────────────────────────────────────────────────────────────────────
QUOTA_CATEGORIES: dict[str, list[str]] = {
    "AIQ":          ["GEN", "OBC", "EWS", "SC", "ST", "GEN-PwD", "OBC-PwD", "EWS-PwD", "SC-PwD", "ST-PwD"],
    "AMU":          ["GEN", "OBC", "EWS", "SC", "ST"],
    "BHU":          ["GEN", "OBC", "EWS", "SC", "ST"],
    "DU":           ["GEN", "OBC", "EWS", "SC", "ST"],
    "IP":           ["GEN", "OBC", "EWS", "SC", "ST"],
    "JM":           ["GEN", "OBC", "SC", "ST"],
    "MM":           ["GEN", "OBC", "EWS", "SC", "ST"],
    "AFMS":         ["AFMS-Priority III", "AFMS-Priority IV"],
    "AFMS-DNB":     ["AFMS-Priority III", "AFMS-Priority IV"],
    "DNB Post MBBS":["GEN", "OBC", "EWS", "SC", "ST", "GEN-PwD"],
    "NRI":          ["GEN"],
    "MNG":          ["GEN"],
    "NBE Diploma":  ["GEN", "OBC", "SC", "ST"],
}

# Seat weights per category (proportion of available seats)
SEAT_WEIGHT: dict[str, float] = {
    "GEN": 0.50, "OBC": 0.27, "EWS": 0.10, "SC": 0.15, "ST": 0.075,
    "GEN-PwD": 0.01, "OBC-PwD": 0.01, "EWS-PwD": 0.005, "SC-PwD": 0.005, "ST-PwD": 0.003,
    "AFMS-Priority III": 0.50, "AFMS-Priority IV": 0.50,
}

# ─────────────────────────────────────────────────────────────────────────────
# Base rank by (tier, category)
# ─────────────────────────────────────────────────────────────────────────────
BASE_RANK: dict[tuple[int, str], int] = {
    (1, "GEN"): 5,      (1, "OBC"): 600,    (1, "EWS"): 250,    (1, "SC"): 2000,   (1, "ST"): 5000,
    (1, "GEN-PwD"): 80, (1, "OBC-PwD"): 700,(1, "EWS-PwD"): 300,(1, "SC-PwD"): 2200,(1, "ST-PwD"): 5500,
    (1, "AFMS-Priority III"): 200, (1, "AFMS-Priority IV"): 1000,
    (2, "GEN"): 400,    (2, "OBC"): 2500,   (2, "EWS"): 1000,   (2, "SC"): 8000,   (2, "ST"): 18000,
    (2, "GEN-PwD"): 500,(2, "OBC-PwD"): 3000,(2, "EWS-PwD"): 1200,(2, "SC-PwD"): 9000,(2, "ST-PwD"): 20000,
    (2, "AFMS-Priority III"): 1000, (2, "AFMS-Priority IV"): 4000,
    (3, "GEN"): 2000,   (3, "OBC"): 8000,   (3, "EWS"): 4000,   (3, "SC"): 20000,  (3, "ST"): 40000,
    (3, "GEN-PwD"): 2500,(3, "OBC-PwD"): 9000,(3, "EWS-PwD"):4500,(3, "SC-PwD"):22000,(3, "ST-PwD"):42000,
    (3, "AFMS-Priority III"): 3000, (3, "AFMS-Priority IV"): 10000,
    (4, "GEN"): 4000,   (4, "OBC"): 15000,  (4, "EWS"): 8000,   (4, "SC"): 35000,  (4, "ST"): 60000,
    (4, "GEN-PwD"): 5000,(4, "OBC-PwD"):16000,(4, "EWS-PwD"):9000,(4, "SC-PwD"):37000,(4, "ST-PwD"):62000,
    (4, "AFMS-Priority III"): 5000, (4, "AFMS-Priority IV"): 15000,
}

# Max seats per course per institute (by tier)
MAX_SEATS = {1: 8, 2: 6, 3: 4, 4: 3, 5: 2}


def get_courses_for_institute(profile: str, quota: str) -> list[str]:
    courses = list(PROFILE_COURSES.get(profile, PROFILE_COURSES["clinical"]))
    # DNB quotas should only have DNB/Diploma courses
    if quota in ("DNB Post MBBS", "NBE Diploma", "AFMS-DNB"):
        courses = [c for c in courses if c.startswith("DNB") or c.startswith("Diploma") or c.startswith("MCh")]
        if not courses:
            courses = DNB_COURSES[:10]
    elif quota in ("AFMS", "AFMS-DNB"):
        courses = [c for c in courses if c.startswith("MD") or c.startswith("MS") or c.startswith("DNB")]
    return courses


def generate_allotments() -> list[dict]:
    rows = []
    sno = 1
    rng = random.Random(42)

    for inst_name, state, tier, quotas, profile in INSTITUTES:
        inst_short = inst_name.split(",")[0].strip()

        for quota in quotas:
            categories = QUOTA_CATEGORIES.get(quota, ["GEN"])
            courses = get_courses_for_institute(profile, quota)

            # Randomly select a subset of courses to avoid too many combos per institute
            max_courses = {1: len(courses), 2: min(30, len(courses)), 3: min(20, len(courses)), 4: min(12, len(courses)), 5: 10}
            n_courses = max_courses.get(tier, 15)
            selected_courses = rng.sample(courses, min(n_courses, len(courses)))

            for course_raw in selected_courses:
                d = desirability(course_raw)
                max_s = MAX_SEATS.get(tier, 3)
                # Seats per category combo
                avail_cats = [c for c in categories if rng.random() < 0.75]
                if not avail_cats:
                    avail_cats = [categories[0]]

                for category in avail_cats:
                    base = BASE_RANK.get((tier, category), BASE_RANK.get((tier, "GEN"), 5000))
                    course_base = int(base * d)
                    n_seats = rng.randint(1, max_s)
                    window = max(50, int(course_base * 0.15))
                    ranks = sorted(rng.sample(
                        range(max(1, course_base), course_base + window + n_seats),
                        min(n_seats, window + n_seats)
                    ))

                    for rank in ranks:
                        rows.append({
                            "sno": sno,
                            "rank": rank,
                            "quota_raw": quota,
                            "quota_norm": quota,
                            "institute_raw": inst_name,
                            "institute_name": inst_short,
                            "state": state,
                            "course_raw": course_raw,
                            "course_norm": normalize_course(course_raw),
                            "allotted_category_raw": category,
                            "allotted_category_norm": category,
                            "candidate_category_raw": category,
                            "remarks": "",
                            "source_page": 2,
                            "source_row_fingerprint": f"seed_{sno}_{rank}_{inst_short[:10]}",
                        })
                        sno += 1

    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if args.clear:
            db.query(Allotment).delete()
            db.query(RC).delete()
            db.query(IngestionProgress).filter(
                IngestionProgress.dataset_key.like("2025|AIQ%")
            ).delete(synchronize_session=False)
            db.commit()
            print("Cleared.")

        existing = db.query(Allotment).count()
        if existing > 0 and not args.clear:
            print(f"DB already has {existing} rows. Use --clear to reseed.")
            return

        rows = generate_allotments()
        print(f"Generating {len(rows):,} allotment rows...")

        BATCH = 1000
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            db.bulk_insert_mappings(Allotment, [
                {"year": 2025, "counselling_type": "AIQ", "counselling_state": None, "round": 1, **r}
                for r in batch
            ])
            db.commit()
            print(f"  {min(i + BATCH, len(rows)):,}/{len(rows):,} inserted...")

        # Populate ref_courses
        existing_norms = {r.course_norm for r in db.query(RC.course_norm).all()}
        for course_raw in ALL_COURSES:
            course_norm = normalize_course(course_raw)
            if course_norm and course_norm not in existing_norms:
                deg, spec = split_course_degree_specialty(course_norm)
                ctype = classify_course_type(course_norm)
                db.add(RC(course_norm=course_norm, degree=deg, specialty=spec, course_type=ctype))
                existing_norms.add(course_norm)
        # Backfill course_type for any existing ref_courses that lack it
        for rc in db.query(RC).filter(RC.course_type.is_(None)).all():
            rc.course_type = classify_course_type(rc.course_norm)
        db.commit()

        total_rows = db.query(Allotment).count()
        # Approximate groups
        from sqlalchemy import func
        total_groups = db.query(func.count()).select_from(
            db.query(
                Allotment.institute_name, Allotment.course_norm,
                Allotment.quota_norm, Allotment.allotted_category_norm,
            ).distinct().subquery()
        ).scalar()

        print(f"\nDone!")
        print(f"  Total allotment rows : {total_rows:,}")
        print(f"  Closing rank groups  : {total_groups:,}")
        print(f"  Courses              : {len(existing_norms)}")
        print("\nStart the API: uvicorn app.main:app --reload")
    finally:
        db.close()


if __name__ == "__main__":
    main()
