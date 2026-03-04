"""
ORM models. Designed for zero-schema-rewrite extensibility:
  - Add year 2024 → new rows, same schema
  - Add state counselling → counselling_type='STATE', counselling_state='Karnataka'
  - Add rounds 2–4 → new rows, same schema
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, UniqueConstraint, Index
)
from .database import Base


class Allotment(Base):
    __tablename__ = "allotments"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Dataset dimensions (extensibility axes)
    year = Column(Integer, nullable=False)
    counselling_type = Column(String(16), nullable=False)   # AIQ | STATE
    counselling_state = Column(String(64), nullable=True)   # null for AIQ
    round = Column(Integer, nullable=False)

    # Source row fields
    sno = Column(Integer, nullable=True)
    rank = Column(Integer, nullable=True)

    # Quota
    quota_raw = Column(String(64), nullable=True)
    quota_norm = Column(String(16), nullable=True)

    # Institute
    institute_raw = Column(Text, nullable=True)
    institute_name = Column(String(256), nullable=True)
    state = Column(String(64), nullable=True)

    # Course
    course_raw = Column(Text, nullable=True)
    course_norm = Column(String(256), nullable=True)

    # Categories
    allotted_category_raw = Column(String(64), nullable=True)
    allotted_category_norm = Column(String(16), nullable=True)
    candidate_category_raw = Column(String(64), nullable=True)   # modal only

    # Extras
    remarks = Column(Text, nullable=True)
    source_page = Column(Integer, nullable=True)
    source_row_fingerprint = Column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "year", "counselling_type", "counselling_state",
            "round", "source_row_fingerprint",
            name="uq_allotment_fingerprint",
        ),
        Index("ix_allotments_year_round", "year", "round"),
        Index("ix_allotments_rank", "rank"),
        Index("ix_allotments_course_norm", "course_norm"),
        Index("ix_allotments_quota_norm", "quota_norm"),
        Index("ix_allotments_allotted_category_norm", "allotted_category_norm"),
        Index("ix_allotments_state", "state"),
        Index("ix_allotments_institute_name", "institute_name"),
    )


class RefCourse(Base):
    """Auto-populated from distinct course_norm after ingestion."""
    __tablename__ = "ref_courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_norm = Column(String(256), unique=True, nullable=False)
    degree = Column(String(32), nullable=True)
    specialty = Column(String(256), nullable=True)


class IngestionError(Base):
    """Stores rows that failed parsing/normalisation."""
    __tablename__ = "ingestion_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=True)
    counselling_type = Column(String(16), nullable=True)
    counselling_state = Column(String(64), nullable=True)
    round = Column(Integer, nullable=True)
    page_num = Column(Integer, nullable=True)
    row_data = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class IngestionProgress(Base):
    """Resume-safe progress tracker (one row per dataset)."""
    __tablename__ = "ingestion_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_key = Column(String(128), unique=True, nullable=False)
    last_page_completed = Column(Integer, default=0)
    total_rows_inserted = Column(Integer, default=0)
    total_rows_skipped = Column(Integer, default=0)
    status = Column(String(16), default="in_progress")   # in_progress | done | failed
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
