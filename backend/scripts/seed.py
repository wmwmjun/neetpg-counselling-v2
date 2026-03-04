#!/usr/bin/env python3
"""
Seed realistic NEET-PG 2025 Round-1 demo data.
Run from backend/:
    python -m scripts.seed
    python -m scripts.seed --clear   # drop existing data first
"""
import random
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app import models  # noqa
from app.models import Allotment, RefCourse as RefCourseModel, IngestionProgress
from ingestion.normalizers import normalize_course, split_course_degree_specialty

random.seed(42)

# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

# (institute_raw, state, tier)
INSTITUTES = [
    ("AIIMS, New Delhi", "Delhi", 1),
    ("AIIMS, Bhopal", "Madhya Pradesh", 1),
    ("ABVIMS & Dr. Ram Manohar Lohia Hospital, New Delhi", "Delhi", 2),
    ("VMMC & Safdarjung Hospital, New Delhi", "Delhi", 2),
    ("Maulana Azad Medical College & Associated Hospitals, New Delhi", "Delhi", 2),
    ("University College of Medical Sciences & GTB Hospital, Delhi", "Delhi", 2),
    ("Lady Hardinge Medical College & Associated Hospitals, New Delhi", "Delhi", 2),
    ("Government Medical College, Chandigarh", "Chandigarh", 2),
    ("BJ Medical College, Ahmedabad", "Gujarat", 2),
    ("Grant Medical College & Sir J.J. Group of Hospitals, Mumbai", "Maharashtra", 2),
    ("Govt. Medical College, Thiruvananthapuram", "Kerala", 3),
    ("Government Medical College, Kozhikode", "Kerala", 3),
    ("Kasturba Medical College, Mangalore", "Karnataka", 3),
    ("MS Ramaiah Medical College, Bangalore", "Karnataka", 3),
    ("Osmania Medical College, Hyderabad", "Telangana", 3),
    ("Government Medical College, Nagpur", "Maharashtra", 3),
    ("IPGMER & SSKM Hospital, Kolkata", "West Bengal", 3),
    ("Government Medical College & Hospital, Chandigarh", "Chandigarh", 2),
    ("Pt. BD Sharma PGIMS, Rohtak", "Haryana", 3),
    ("SMS Medical College, Jaipur", "Rajasthan", 3),
]

# (course_raw, degree)  – keep degree explicit for seat-count logic
COURSES = [
    ("MD General Medicine", "MD"),
    ("MD Dermatology, Venereology & Leprosy", "MD"),
    ("MD Radio Diagnosis", "MD"),
    ("MD Paediatrics", "MD"),
    ("MD Psychiatry", "MD"),
    ("MD Anaesthesiology", "MD"),
    ("MD Obstetrics and Gynaecology", "MD"),
    ("MD Pathology", "MD"),
    ("MD Biochemistry", "MD"),
    ("MD Physiology", "MD"),
    ("MS General Surgery", "MS"),
    ("MS Orthopaedics", "MS"),
    ("MS Ophthalmology", "MS"),
    ("MS Otorhinolaryngology (ENT)", "MS"),
    ("MS Obstetrics and Gynaecology", "MS"),
    ("DNB General Medicine", "DNB"),
    ("DNB Radio Diagnosis", "DNB"),
    ("DNB General Surgery", "DNB"),
]

CATEGORIES = ["GN", "EW", "BC", "SC", "ST"]

# Quota: MVP uses AI only (AM only for AIIMS)
QUOTAS = ["AI"]

# Seats available per tier + course desirability
SEATS = {
    ("MD General Medicine", 1): 8, ("MD General Medicine", 2): 6, ("MD General Medicine", 3): 4,
    ("MD Dermatology, Venereology & Leprosy", 1): 4, ("MD Dermatology, Venereology & Leprosy", 2): 3, ("MD Dermatology, Venereology & Leprosy", 3): 2,
    ("MD Radio Diagnosis", 1): 6, ("MD Radio Diagnosis", 2): 5, ("MD Radio Diagnosis", 3): 3,
    ("MD Paediatrics", 1): 6, ("MD Paediatrics", 2): 5, ("MD Paediatrics", 3): 3,
    ("MD Psychiatry", 1): 3, ("MD Psychiatry", 2): 3, ("MD Psychiatry", 3): 2,
    ("MD Anaesthesiology", 1): 8, ("MD Anaesthesiology", 2): 6, ("MD Anaesthesiology", 3): 5,
    ("MD Obstetrics and Gynaecology", 1): 6, ("MD Obstetrics and Gynaecology", 2): 5, ("MD Obstetrics and Gynaecology", 3): 4,
    ("MD Pathology", 1): 6, ("MD Pathology", 2): 5, ("MD Pathology", 3): 4,
    ("MD Biochemistry", 1): 4, ("MD Biochemistry", 2): 3, ("MD Biochemistry", 3): 3,
    ("MD Physiology", 1): 4, ("MD Physiology", 2): 3, ("MD Physiology", 3): 3,
    ("MS General Surgery", 1): 6, ("MS General Surgery", 2): 5, ("MS General Surgery", 3): 4,
    ("MS Orthopaedics", 1): 5, ("MS Orthopaedics", 2): 4, ("MS Orthopaedics", 3): 3,
    ("MS Ophthalmology", 1): 3, ("MS Ophthalmology", 2): 3, ("MS Ophthalmology", 3): 2,
    ("MS Otorhinolaryngology (ENT)", 1): 3, ("MS Otorhinolaryngology (ENT)", 2): 2, ("MS Otorhinolaryngology (ENT)", 3): 2,
    ("MS Obstetrics and Gynaecology", 1): 5, ("MS Obstetrics and Gynaecology", 2): 4, ("MS Obstetrics and Gynaecology", 3): 3,
    ("DNB General Medicine", 1): 0, ("DNB General Medicine", 2): 4, ("DNB General Medicine", 3): 6,
    ("DNB Radio Diagnosis", 1): 0, ("DNB Radio Diagnosis", 2): 3, ("DNB Radio Diagnosis", 3): 4,
    ("DNB General Surgery", 1): 0, ("DNB General Surgery", 2): 3, ("DNB General Surgery", 3): 4,
}

# Base rank for (tier, category) – the lowest (most competitive) rank for that combo
BASE_RANK = {
    (1, "GN"):  1,   (1, "EW"):  250, (1, "BC"):  600, (1, "SC"):  2000, (1, "ST"): 5000,
    (2, "GN"):  300, (2, "EW"):  800, (2, "BC"): 2000, (2, "SC"):  6000, (2, "ST"):15000,
    (3, "GN"): 1500, (3, "EW"): 3500, (3, "BC"): 6000, (3, "SC"): 15000, (3, "ST"):30000,
}

# Course desirability multiplier (lower = more competitive)
COURSE_MULTIPLIER = {
    "MD General Medicine": 1.0,
    "MD Dermatology, Venereology & Leprosy": 0.4,   # very competitive
    "MD Radio Diagnosis": 0.6,
    "MD Paediatrics": 1.2,
    "MD Psychiatry": 2.5,
    "MD Anaesthesiology": 2.0,
    "MD Obstetrics and Gynaecology": 1.3,
    "MD Pathology": 3.0,
    "MD Biochemistry": 4.0,
    "MD Physiology": 4.5,
    "MS General Surgery": 1.1,
    "MS Orthopaedics": 0.9,
    "MS Ophthalmology": 1.5,
    "MS Otorhinolaryngology (ENT)": 2.0,
    "MS Obstetrics and Gynaecology": 1.3,
    "DNB General Medicine": 1.4,
    "DNB Radio Diagnosis": 0.9,
    "DNB General Surgery": 1.5,
}


def generate_allotments():
    rows = []
    sno = 1
    for institute_raw, state, tier in INSTITUTES:
        institute_name = institute_raw.split(",")[0].strip()
        for course_raw, degree in COURSES:
            seats = SEATS.get((course_raw, tier), 0)
            if seats == 0:
                continue
            for category in CATEGORIES:
                base = BASE_RANK[(tier, category)]
                multiplier = COURSE_MULTIPLIER.get(course_raw, 1.5)
                course_base = int(base * multiplier)
                # Not all seats may be filled for every category
                filled = max(1, int(seats * {
                    "GN": 0.5, "EW": 0.15, "BC": 0.27, "SC": 0.15, "ST": 0.075
                }.get(category, 0.1) + random.uniform(-0.5, 0.5)))
                filled = max(1, min(filled, seats))
                # Generate individual ranks (spread from base to base + window)
                window = int(course_base * 0.25 + 200)
                ranks = sorted(random.sample(
                    range(course_base, course_base + window),
                    min(filled, window)
                ))
                for rank in ranks:
                    rows.append({
                        "sno": sno,
                        "rank": rank,
                        "quota_raw": "AI",
                        "quota_norm": "AI",
                        "institute_raw": institute_raw,
                        "institute_name": institute_name,
                        "state": state,
                        "course_raw": course_raw,
                        "course_norm": normalize_course(course_raw),
                        "allotted_category_raw": category,
                        "allotted_category_norm": category,
                        "candidate_category_raw": category,
                        "remarks": "",
                        "source_page": 2,
                        "source_row_fingerprint": f"seed_{sno}_{rank}_{institute_name}",
                    })
                    sno += 1
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear existing allotments first")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if args.clear:
            db.query(Allotment).delete()
            db.query(RefCourseModel).delete()
            db.query(IngestionProgress).filter_by(dataset_key="2025|AIQ|AIQ|1").delete()
            db.commit()
            print("Cleared existing data.")

        existing = db.query(Allotment).count()
        if existing > 0 and not args.clear:
            print(f"DB already has {existing} rows. Use --clear to reseed.")
            return

        rows = generate_allotments()
        print(f"Generating {len(rows)} allotment rows...")

        for i, row in enumerate(rows):
            db.add(Allotment(
                year=2025,
                counselling_type="AIQ",
                counselling_state=None,
                round=1,
                **row,
            ))
            if (i + 1) % 500 == 0:
                db.commit()
                print(f"  {i + 1}/{len(rows)} inserted...")

        db.commit()

        # Populate ref_courses
        for course_raw, degree in COURSES:
            course_norm = normalize_course(course_raw)
            deg, specialty = split_course_degree_specialty(course_norm)
            if not db.query(RefCourseModel).filter_by(course_norm=course_norm).first():
                db.add(RefCourseModel(course_norm=course_norm, degree=deg, specialty=specialty))
        db.commit()

        total = db.query(Allotment).count()
        print(f"\nDone! Total allotments in DB: {total}")
        print("Now run: cd backend && uvicorn app.main:app --reload")
    finally:
        db.close()


if __name__ == "__main__":
    main()
