#!/usr/bin/env python3
"""
One-time migration:
  1. Add course_type column to ref_courses (if missing)
  2. Rebuild ref_courses from actual allotments data (remove orphans, add missing)
  3. Populate course_type and degree/specialty for all rows

Run from backend/:
    python3 -m scripts.migrate_course_type
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text, func
from app.database import SessionLocal, engine
from app.models import Allotment, RefCourse
from ingestion.normalizers import classify_course_type, split_course_degree_specialty


def main():
    # 1. Add column if it doesn't exist (works with both SQLite and PostgreSQL)
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("ref_courses")}
    if "course_type" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE ref_courses ADD COLUMN course_type VARCHAR(32)"))
            conn.commit()
        print("Added course_type column to ref_courses.")
    else:
        print("course_type column already exists.")

    db = SessionLocal()
    try:
        # 2. Get all distinct course_norm values actually used in allotments
        used_courses = {
            row[0] for row in
            db.query(Allotment.course_norm).distinct().all()
            if row[0] and row[0].strip()
        }
        print(f"Courses used in allotments: {len(used_courses)}")

        # Get current ref_courses
        existing_ref = {rc.course_norm: rc for rc in db.query(RefCourse).all()}
        print(f"Current ref_courses rows: {len(existing_ref)}")

        # 3. Delete orphaned ref_courses (not used by any allotment)
        orphans = set(existing_ref.keys()) - used_courses
        if orphans:
            db.query(RefCourse).filter(RefCourse.course_norm.in_(orphans)).delete(synchronize_session="fetch")
            print(f"Removed {len(orphans)} orphaned ref_courses.")

        # 4. Add missing courses (used in allotments but not in ref_courses)
        missing = used_courses - set(existing_ref.keys())
        for course_norm in missing:
            deg, spec = split_course_degree_specialty(course_norm)
            ctype = classify_course_type(course_norm)
            db.add(RefCourse(course_norm=course_norm, degree=deg, specialty=spec, course_type=ctype))
        if missing:
            print(f"Added {len(missing)} missing ref_courses.")

        db.commit()

        # 5. Populate course_type for all rows (including pre-existing ones)
        updated = 0
        for rc in db.query(RefCourse).all():
            new_type = classify_course_type(rc.course_norm)
            if rc.course_type != new_type:
                rc.course_type = new_type
                updated += 1
            # Also fix degree/specialty if missing
            if not rc.degree:
                deg, spec = split_course_degree_specialty(rc.course_norm)
                rc.degree = deg
                rc.specialty = spec
        db.commit()
        if updated:
            print(f"Updated {updated} rows with course_type.")

        # Summary
        total = db.query(RefCourse).count()
        print(f"\nTotal ref_courses: {total}")
        for ct, count in db.query(RefCourse.course_type, func.count()).group_by(RefCourse.course_type).order_by(RefCourse.course_type).all():
            print(f"  {ct}: {count} courses")
    finally:
        db.close()


if __name__ == "__main__":
    main()
