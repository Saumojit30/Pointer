"""
RolePointer — SQLAlchemy Database Models
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rolepointer.db.engine import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class JobListingORM(Base):
    __tablename__ = "job_listings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    workplace_type: Mapped[str] = mapped_column(String, default="REMOTE")
    domain: Mapped[str] = mapped_column(String, default="Backend")
    experience_level: Mapped[str] = mapped_column(String, default="SENIOR")
    salary_range: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="Direct")
    triage_status: Mapped[str] = mapped_column(String, default="discovered")
    posted_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    evaluation: Mapped[FitEvaluationORM | None] = relationship(back_populates="job", uselist=False, cascade="all, delete-orphan")
    tailored_package: Mapped[TailoredPackageORM | None] = relationship(back_populates="job", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_job_domain", "domain"),
        Index("ix_job_status", "triage_status"),
        Index("ix_job_location", "country", "city"),
    )


class FitEvaluationORM(Base):
    __tablename__ = "fit_evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_listings.id"), nullable=False, unique=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    match_tier: Mapped[str] = mapped_column(String, default="STRONG")
    pros_json: Mapped[str] = mapped_column(Text, default="[]")
    cons_json: Mapped[str] = mapped_column(Text, default="[]")
    dealbreakers_json: Mapped[str] = mapped_column(Text, default="[]")
    has_dealbreaker: Mapped[bool] = mapped_column(Boolean, default=False)
    matching_skills_json: Mapped[str] = mapped_column(Text, default="[]")
    missing_skills_json: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str] = mapped_column(Text, default="")
    ghost_json: Mapped[str] = mapped_column(Text, default="{}")
    salary_norm_json: Mapped[str] = mapped_column(Text, default="{}")
    work_auth_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    job: Mapped[JobListingORM] = relationship(back_populates="evaluation")


class TailoredPackageORM(Base):
    __tablename__ = "tailored_packages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_listings.id"), nullable=False, unique=True)
    tailored_summary: Mapped[str] = mapped_column(Text, default="")
    tailored_bullets_json: Mapped[str] = mapped_column(Text, default="[]")
    targeted_skills_json: Mapped[str] = mapped_column(Text, default="[]")
    direct_pitch_letter: Mapped[str] = mapped_column(Text, default="")
    ats_score: Mapped[int] = mapped_column(Integer, default=90)
    audit_json: Mapped[str] = mapped_column(Text, default="{}")
    pdf_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    job: Mapped[JobListingORM] = relationship(back_populates="tailored_package")


class UserProfileORM(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default_user")
    name: Mapped[str] = mapped_column(String, default="Alex Morgan")
    email: Mapped[str] = mapped_column(String, default="alex.morgan@example.com")
    phone: Mapped[str] = mapped_column(String, default="+1 (555) 234-5678")
    location: Mapped[str] = mapped_column(String, default="San Francisco, CA")
    country_pref_json: Mapped[str] = mapped_column(Text, default="[]")
    city_pref_json: Mapped[str] = mapped_column(Text, default="[]")
    workplace_types_json: Mapped[str] = mapped_column(Text, default="[]")
    target_domains_json: Mapped[str] = mapped_column(Text, default="[]")
    target_roles_json: Mapped[str] = mapped_column(Text, default="[]")
    skills_json: Mapped[Text] = mapped_column(Text, default="[]")
    experience_summary: Mapped[str] = mapped_column(Text, default="")
    min_salary_floor: Mapped[float | None] = mapped_column(Float, nullable=True)
    dealbreakers_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class InterviewSessionORM(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    questions_json: Mapped[str] = mapped_column(Text, default="[]")
    evaluations_json: Mapped[str] = mapped_column(Text, default="[]")
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ApplicationRecordORM(Base):
    __tablename__ = "application_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    company: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    days_since_applied: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="awaiting_reply")
    follow_up_due: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0)
    last_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    direct_pitch_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
