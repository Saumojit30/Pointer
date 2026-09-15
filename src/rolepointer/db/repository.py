"""
RolePointer — Database Repository & Persistence Layer
Handles SQLite WAL persistence, thread-safe session management,
and bidirectional conversion between SQLAlchemy ORM models and Pydantic schemas.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from rolepointer.db.engine import Base, engine, SessionLocal
from rolepointer.db.models import (
    JobListingORM, FitEvaluationORM, TailoredPackageORM,
    UserProfileORM, InterviewSessionORM, ApplicationRecordORM
)
from rolepointer.models.schemas import (
    JobListing, UserProfile, FitEvaluation, TailoredPackage,
    ReviewAuditResult, MockInterviewSession, MockInterviewQuestion,
    MockInterviewEvaluation, ApplicationRecord, TriageStatus,
    WorkplaceType, ExperienceLevel, DealbreakerAlert
)


def init_db() -> None:
    """Creates all database tables in SQLite WAL mode."""
    logger.info("[DB] Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("[DB] Database schema initialized.")


def _safe_json_loads(data: Optional[str], default: any) -> any:
    if not data:
        return default
    try:
        return json.loads(data)
    except Exception:
        return default


# ── Job Listings & Fit Evaluations ───────────────────────────────────────────

def save_job(job: JobListing, eval_res: Optional[FitEvaluation] = None) -> None:
    """Upserts a JobListing and optional FitEvaluation into the database."""
    with SessionLocal() as session:
        existing_job = session.query(JobListingORM).filter_by(id=job.id).first()
        if not existing_job:
            existing_job = JobListingORM(
                id=job.id,
                title=job.title,
                company=job.company,
                location=job.location,
                country=job.country,
                city=job.city,
                workplace_type=job.workplace_type.value if hasattr(job.workplace_type, "value") else str(job.workplace_type),
                domain=job.domain,
                experience_level=job.experience_level.value if hasattr(job.experience_level, "value") else str(job.experience_level),
                salary_range=job.salary_range,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                tags_json=json.dumps(job.tags),
                description=job.description,
                url=job.url,
                source=job.source,
                triage_status=job.triage_status.value if hasattr(job.triage_status, "value") else str(job.triage_status),
                posted_at=job.posted_at,
            )
            session.add(existing_job)
        else:
            existing_job.title = job.title
            existing_job.company = job.company
            existing_job.location = job.location
            existing_job.country = job.country
            existing_job.city = job.city
            existing_job.workplace_type = job.workplace_type.value if hasattr(job.workplace_type, "value") else str(job.workplace_type)
            existing_job.domain = job.domain
            existing_job.experience_level = job.experience_level.value if hasattr(job.experience_level, "value") else str(job.experience_level)
            existing_job.salary_range = job.salary_range
            existing_job.salary_min = job.salary_min
            existing_job.salary_max = job.salary_max
            existing_job.tags_json = json.dumps(job.tags)
            existing_job.description = job.description
            existing_job.url = job.url
            existing_job.source = job.source
            existing_job.triage_status = job.triage_status.value if hasattr(job.triage_status, "value") else str(job.triage_status)

        if eval_res:
            existing_eval = session.query(FitEvaluationORM).filter_by(job_id=job.id).first()
            dealbreaker_dicts = [d.model_dump() for d in eval_res.dealbreaker_alerts]
            if not existing_eval:
                existing_eval = FitEvaluationORM(
                    job_id=job.id,
                    score=eval_res.score,
                    match_tier=eval_res.match_tier,
                    pros_json=json.dumps(eval_res.pros),
                    cons_json=json.dumps(eval_res.cons),
                    dealbreakers_json=json.dumps(dealbreaker_dicts),
                    has_dealbreaker=eval_res.has_dealbreaker,
                    matching_skills_json=json.dumps(eval_res.matching_skills),
                    missing_skills_json=json.dumps(eval_res.missing_skills),
                    summary=eval_res.summary,
                )
                session.add(existing_eval)
            else:
                existing_eval.score = eval_res.score
                existing_eval.match_tier = eval_res.match_tier
                existing_eval.pros_json = json.dumps(eval_res.pros)
                existing_eval.cons_json = json.dumps(eval_res.cons)
                existing_eval.dealbreakers_json = json.dumps(dealbreaker_dicts)
                existing_eval.has_dealbreaker = eval_res.has_dealbreaker
                existing_eval.matching_skills_json = json.dumps(eval_res.matching_skills)
                existing_eval.missing_skills_json = json.dumps(eval_res.missing_skills)
                existing_eval.summary = eval_res.summary

        session.commit()


def get_all_jobs_with_evaluations() -> List[Tuple[JobListing, Optional[FitEvaluation]]]:
    """Retrieves all persisted jobs and their fit evaluations."""
    results: List[Tuple[JobListing, Optional[FitEvaluation]]] = []
    with SessionLocal() as session:
        orm_jobs = session.query(JobListingORM).all()
        for orm_job in orm_jobs:
            job = JobListing(
                id=orm_job.id,
                title=orm_job.title,
                company=orm_job.company,
                location=orm_job.location,
                country=orm_job.country,
                city=orm_job.city,
                workplace_type=WorkplaceType(orm_job.workplace_type) if orm_job.workplace_type in WorkplaceType.__members__.values() else WorkplaceType.REMOTE,
                domain=orm_job.domain,
                experience_level=ExperienceLevel(orm_job.experience_level) if orm_job.experience_level in ExperienceLevel.__members__.values() else ExperienceLevel.SENIOR,
                salary_range=orm_job.salary_range,
                salary_min=orm_job.salary_min,
                salary_max=orm_job.salary_max,
                tags=_safe_json_loads(orm_job.tags_json, []),
                description=orm_job.description,
                url=orm_job.url,
                source=orm_job.source,
                triage_status=TriageStatus(orm_job.triage_status) if orm_job.triage_status in TriageStatus.__members__.values() else TriageStatus.DISCOVERED,
                posted_at=orm_job.posted_at,
            )
            eval_res = None
            if orm_job.evaluation:
                oe = orm_job.evaluation
                raw_db = _safe_json_loads(oe.dealbreakers_json, [])
                alerts = [DealbreakerAlert(**d) for d in raw_db]
                eval_res = FitEvaluation(
                    job_id=oe.job_id,
                    score=oe.score,
                    match_tier=oe.match_tier,
                    pros=_safe_json_loads(oe.pros_json, []),
                    cons=_safe_json_loads(oe.cons_json, []),
                    dealbreaker_alerts=alerts,
                    has_dealbreaker=oe.has_dealbreaker,
                    matching_skills=_safe_json_loads(oe.matching_skills_json, []),
                    missing_skills=_safe_json_loads(oe.missing_skills_json, []),
                    summary=oe.summary,
                )
            results.append((job, eval_res))
    return results


# ── Application Records (Response Radar) ──────────────────────────────────────

def save_application(record: ApplicationRecord) -> None:
    """Upserts an ApplicationRecord."""
    with SessionLocal() as session:
        existing = session.query(ApplicationRecordORM).filter_by(job_id=record.job_id).first()
        status_val = record.status.value if hasattr(record.status, "value") else str(record.status)
        if not existing:
            existing = ApplicationRecordORM(
                id=record.id,
                job_id=record.job_id,
                company=record.company,
                title=record.title,
                applied_at=record.applied_at,
                days_since_applied=record.days_since_applied,
                status=status_val,
                follow_up_due=record.follow_up_due,
                follow_up_count=record.follow_up_count,
                last_follow_up_at=record.last_follow_up_at,
                direct_pitch_letter=record.direct_pitch_letter,
            )
            session.add(existing)
        else:
            existing.company = record.company
            existing.title = record.title
            existing.applied_at = record.applied_at
            existing.days_since_applied = record.days_since_applied
            existing.status = status_val
            existing.follow_up_due = record.follow_up_due
            existing.follow_up_count = record.follow_up_count
            existing.last_follow_up_at = record.last_follow_up_at
            existing.direct_pitch_letter = record.direct_pitch_letter
        session.commit()


def get_all_applications() -> Dict[str, ApplicationRecord]:
    """Retrieves all persisted applications keyed by job_id."""
    apps: Dict[str, ApplicationRecord] = {}
    with SessionLocal() as session:
        records = session.query(ApplicationRecordORM).all()
        for r in records:
            apps[r.job_id] = ApplicationRecord(
                id=r.id,
                job_id=r.job_id,
                company=r.company,
                title=r.title,
                applied_at=r.applied_at,
                days_since_applied=r.days_since_applied,
                status=TriageStatus(r.status) if r.status in TriageStatus.__members__.values() else TriageStatus.AWAITING_REPLY,
                follow_up_due=r.follow_up_due,
                follow_up_count=r.follow_up_count,
                last_follow_up_at=r.last_follow_up_at,
                direct_pitch_letter=r.direct_pitch_letter,
            )
    return apps


# ── Tailored Packages ─────────────────────────────────────────────────────────

def save_tailored_package(pkg: TailoredPackage) -> None:
    """Upserts a TailoredPackage."""
    with SessionLocal() as session:
        existing = session.query(TailoredPackageORM).filter_by(job_id=pkg.job_id).first()
        audit_dict = pkg.audit_result.model_dump()
        if not existing:
            existing = TailoredPackageORM(
                id=pkg.id,
                job_id=pkg.job_id,
                tailored_summary=pkg.tailored_summary,
                tailored_bullets_json=json.dumps(pkg.tailored_experience_bullets),
                targeted_skills_json=json.dumps(pkg.targeted_skills),
                direct_pitch_letter=pkg.direct_pitch_letter,
                ats_score=pkg.audit_result.ats_score,
                audit_json=json.dumps(audit_dict),
                pdf_filename=pkg.pdf_filename,
                created_at=pkg.created_at,
            )
            session.add(existing)
        else:
            existing.tailored_summary = pkg.tailored_summary
            existing.tailored_bullets_json = json.dumps(pkg.tailored_experience_bullets)
            existing.targeted_skills_json = json.dumps(pkg.targeted_skills)
            existing.direct_pitch_letter = pkg.direct_pitch_letter
            existing.ats_score = pkg.audit_result.ats_score
            existing.audit_json = json.dumps(audit_dict)
            existing.pdf_filename = pkg.pdf_filename
        session.commit()


def get_all_tailored_packages() -> Dict[str, TailoredPackage]:
    """Retrieves all persisted TailoredPackages keyed by job_id."""
    packages: Dict[str, TailoredPackage] = {}
    with SessionLocal() as session:
        records = session.query(TailoredPackageORM).all()
        for r in records:
            audit_raw = _safe_json_loads(r.audit_json, {})
            audit_obj = ReviewAuditResult(**audit_raw) if audit_raw else ReviewAuditResult(ats_score=r.ats_score)
            
            # Look up company and title from job
            comp = r.job.company if r.job else "Target Company"
            titl = r.job.title if r.job else "Target Role"

            packages[r.job_id] = TailoredPackage(
                id=r.id,
                job_id=r.job_id,
                company=comp,
                title=titl,
                tailored_summary=r.tailored_summary,
                tailored_experience_bullets=_safe_json_loads(r.tailored_bullets_json, []),
                targeted_skills=_safe_json_loads(r.targeted_skills_json, []),
                direct_pitch_letter=r.direct_pitch_letter,
                audit_result=audit_obj,
                pdf_filename=r.pdf_filename,
                created_at=r.created_at,
            )
    return packages


# ── User Profile ─────────────────────────────────────────────────────────────

def save_user_profile(profile: UserProfile) -> None:
    """Upserts the UserProfile."""
    with SessionLocal() as session:
        existing = session.query(UserProfileORM).filter_by(id=profile.id).first()
        workplace_vals = [w.value if hasattr(w, "value") else str(w) for w in profile.preferred_workplace_types]
        if not existing:
            existing = UserProfileORM(
                id=profile.id,
                name=profile.name,
                email=profile.email,
                phone=profile.phone,
                location=profile.location,
                country_pref_json=json.dumps(profile.country_preference),
                city_pref_json=json.dumps(profile.city_preference),
                workplace_types_json=json.dumps(workplace_vals),
                target_domains_json=json.dumps(profile.target_domains),
                target_roles_json=json.dumps(profile.target_roles),
                skills_json=json.dumps(profile.skills),
                experience_summary=profile.experience_summary,
                min_salary_floor=profile.min_salary_floor,
                dealbreakers_json=json.dumps(profile.dealbreakers),
            )
            session.add(existing)
        else:
            existing.name = profile.name
            existing.email = profile.email
            existing.phone = profile.phone
            existing.location = profile.location
            existing.country_pref_json = json.dumps(profile.country_preference)
            existing.city_pref_json = json.dumps(profile.city_preference)
            existing.workplace_types_json = json.dumps(workplace_vals)
            existing.target_domains_json = json.dumps(profile.target_domains)
            existing.target_roles_json = json.dumps(profile.target_roles)
            existing.skills_json = json.dumps(profile.skills)
            existing.experience_summary = profile.experience_summary
            existing.min_salary_floor = profile.min_salary_floor
            existing.dealbreakers_json = json.dumps(profile.dealbreakers)
        session.commit()


def get_user_profile(profile_id: str = "default_user") -> Optional[UserProfile]:
    """Retrieves the UserProfile from database."""
    with SessionLocal() as session:
        orm = session.query(UserProfileORM).filter_by(id=profile_id).first()
        if not orm:
            return None
        raw_wp = _safe_json_loads(orm.workplace_types_json, [])
        wps = [WorkplaceType(w) if w in WorkplaceType.__members__.values() else WorkplaceType.REMOTE for w in raw_wp]
        return UserProfile(
            id=orm.id,
            name=orm.name,
            email=orm.email,
            phone=orm.phone,
            location=orm.location,
            country_preference=_safe_json_loads(orm.country_pref_json, []),
            city_preference=_safe_json_loads(orm.city_pref_json, []),
            preferred_workplace_types=wps,
            target_domains=_safe_json_loads(orm.target_domains_json, []),
            target_roles=_safe_json_loads(orm.target_roles_json, []),
            skills=_safe_json_loads(orm.skills_json, []),
            experience_summary=orm.experience_summary,
            min_salary_floor=orm.min_salary_floor,
            dealbreakers=_safe_json_loads(orm.dealbreakers_json, []),
        )


# ── Mock Interview Sessions ───────────────────────────────────────────────────

def save_interview_session(session_data: MockInterviewSession) -> None:
    """Upserts a MockInterviewSession."""
    with SessionLocal() as session:
        existing = session.query(InterviewSessionORM).filter_by(id=session_data.session_id).first()
        q_dicts = [q.model_dump() for q in session_data.questions]
        e_dicts = [e.model_dump() for e in session_data.evaluations]
        if not existing:
            existing = InterviewSessionORM(
                id=session_data.session_id,
                job_id=session_data.job_id,
                company=session_data.company,
                role=session_data.role,
                questions_json=json.dumps(q_dicts),
                evaluations_json=json.dumps(e_dicts),
                overall_score=session_data.overall_score,
                created_at=session_data.created_at,
            )
            session.add(existing)
        else:
            existing.questions_json = json.dumps(q_dicts)
            existing.evaluations_json = json.dumps(e_dicts)
            existing.overall_score = session_data.overall_score
        session.commit()


def get_interview_session(session_id: str) -> Optional[MockInterviewSession]:
    """Retrieves a MockInterviewSession by session_id."""
    with SessionLocal() as session:
        orm = session.query(InterviewSessionORM).filter_by(id=session_id).first()
        if not orm:
            return None
        raw_q = _safe_json_loads(orm.questions_json, [])
        raw_e = _safe_json_loads(orm.evaluations_json, [])
        return MockInterviewSession(
            session_id=orm.id,
            job_id=orm.job_id,
            company=orm.company,
            role=orm.role,
            questions=[MockInterviewQuestion(**q) for q in raw_q],
            evaluations=[MockInterviewEvaluation(**e) for e in raw_e],
            overall_score=orm.overall_score,
            created_at=orm.created_at,
        )
