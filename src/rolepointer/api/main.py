"""
RolePointer — FastAPI Application & Orchestration Gateway
REST Endpoints, Real-Time SSE Streams, Executive Morning Briefing,
and Application Response Radar with Value-Add Follow-Up Generator.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from rolepointer.core.settings import settings
from rolepointer.models.schemas import (
    JobListing, UserProfile, FitEvaluation, TailoredPackage, ReviewAuditResult,
    MockInterviewSession, MockInterviewQuestion, MockInterviewEvaluation,
    TriageStatus, WorkplaceType, FeedFilterQuery, ExecutiveBriefing,
    ApplicationRecord, FollowUpDraft
)
from rolepointer.feeds.mock_feeds import get_mock_jobs
from rolepointer.feeds.remote_feeds import fetch_jobicy_jobs, fetch_remoteok_jobs
from rolepointer.feeds.location_feeds import fetch_arbeitnow_jobs, filter_by_location
from rolepointer.feeds.hn_hiring_feed import fetch_hn_hiring_jobs
from rolepointer.feeds.url_parser import parse_job_url
from rolepointer.agents.fit_evaluator import evaluate_job_fit
from rolepointer.agents.drafter import draft_tailored_package
from rolepointer.agents.reviewer import audit_tailored_package
from rolepointer.agents.briefing_agent import generate_executive_briefing
from rolepointer.agents.followup_agent import generate_value_add_followup
from rolepointer.agents.interview_agent import (
    generate_mock_interview_questions, evaluate_interview_answer
)
from rolepointer.compiler.pdf_engine import compile_ats_resume_pdf, OUTPUT_DIR


app = FastAPI(
    title="RolePointer API",
    description="Autonomous Job Discovery, Guardrail Triage & Tailored Career Pipeline",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-Memory Repository ──────────────────────────────────────────────────────
CURRENT_PROFILE: UserProfile = UserProfile()
JOBS_STORE: Dict[str, JobListing] = {}
EVALUATIONS_STORE: Dict[str, FitEvaluation] = {}
PACKAGES_STORE: Dict[str, TailoredPackage] = {}
INTERVIEWS_STORE: Dict[str, MockInterviewSession] = {}
APPLICATIONS_STORE: Dict[str, ApplicationRecord] = {}
SSE_QUEUE: asyncio.Queue = asyncio.Queue()


def _populate_initial_data():
    """Seed with mock jobs, auto-precompile packages for top matches, and seed pipeline radar."""
    for job in get_mock_jobs():
        JOBS_STORE[job.id] = job
        eval_res = evaluate_job_fit(job, CURRENT_PROFILE)
        EVALUATIONS_STORE[job.id] = eval_res

    # Seed 1 active application in Awaiting Reply (Day 2)
    job1 = JOBS_STORE.get("mock-job-01")
    if job1:
        job1.triage_status = TriageStatus.AWAITING_REPLY
        APPLICATIONS_STORE[job1.id] = ApplicationRecord(
            job_id=job1.id,
            company=job1.company,
            title=job1.title,
            applied_at=datetime.now(timezone.utc) - timedelta(days=2),
            days_since_applied=2,
            status=TriageStatus.AWAITING_REPLY,
            follow_up_due=False,
            follow_up_count=0,
        )

    # Seed 1 active application in Follow-Up Due (Day 6 without reply)
    job2 = JOBS_STORE.get("mock-job-02")
    if job2:
        job2.triage_status = TriageStatus.FOLLOW_UP_DUE
        APPLICATIONS_STORE[job2.id] = ApplicationRecord(
            job_id=job2.id,
            company=job2.company,
            title=job2.title,
            applied_at=datetime.now(timezone.utc) - timedelta(days=6),
            days_since_applied=6,
            status=TriageStatus.FOLLOW_UP_DUE,
            follow_up_due=True,
            follow_up_count=0,
        )


_populate_initial_data()


# ── Profile Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/profile", response_model=UserProfile)
def get_profile():
    return CURRENT_PROFILE


@app.post("/api/profile", response_model=UserProfile)
def update_profile(profile: UserProfile):
    global CURRENT_PROFILE
    CURRENT_PROFILE = profile
    for job_id, job in JOBS_STORE.items():
        EVALUATIONS_STORE[job_id] = evaluate_job_fit(job, CURRENT_PROFILE)
    logger.info("[API] Profile updated and jobs re-evaluated")
    return CURRENT_PROFILE


# ── Executive Morning Briefing ───────────────────────────────────────────────

@app.get("/api/briefing", response_model=ExecutiveBriefing)
def get_daily_briefing():
    """Returns the curated Top 3 daily briefing with pre-compiled packages."""
    all_jobs = list(JOBS_STORE.values())
    briefing, _ = generate_executive_briefing(all_jobs, CURRENT_PROFILE, PACKAGES_STORE, top_limit=3)
    return briefing


# ── Job Discovery & Search ───────────────────────────────────────────────────

@app.get("/api/jobs")
def list_jobs(
    domain: Optional[str] = None,
    workplace_type: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[int] = None,
    exclude_dealbreakers: bool = False,
):
    results = []
    for job_id, job in JOBS_STORE.items():
        eval_res = EVALUATIONS_STORE.get(job_id)

        if domain and domain.lower() != "all" and domain.lower() not in job.domain.lower():
            continue
        if workplace_type and workplace_type != "ANY" and job.workplace_type.value != workplace_type:
            continue
        if country and country != "All" and job.country and country.lower() not in job.country.lower():
            continue
        if city and city != "All" and job.city and city.lower() not in job.city.lower():
            continue
        if status and job.triage_status.value != status:
            continue
        if min_score and eval_res and eval_res.score < min_score:
            continue
        if exclude_dealbreakers and eval_res and eval_res.has_dealbreaker:
            continue

        results.append({
            "job": job.model_dump(),
            "evaluation": eval_res.model_dump() if eval_res else None,
            "has_package": job_id in PACKAGES_STORE,
        })

    results.sort(key=lambda x: (x["evaluation"]["score"] if x["evaluation"] else 0), reverse=True)
    return {"total": len(results), "jobs": results}


@app.post("/api/jobs/discover")
async def trigger_discovery():
    discovered_count = 0
    all_incoming: List[JobListing] = []

    if settings.use_mock_feeds:
        all_incoming.extend(get_mock_jobs())
    else:
        try:
            remote_jobs = fetch_jobicy_jobs(count=10) + fetch_remoteok_jobs(count=10)
            all_incoming.extend(remote_jobs)
        except Exception as e:
            logger.warning(f"Remote feed error: {e}")

        try:
            loc_jobs = fetch_arbeitnow_jobs(count=10)
            all_incoming.extend(loc_jobs)
        except Exception as e:
            logger.warning(f"Location feed error: {e}")

        try:
            hn_jobs = fetch_hn_hiring_jobs(limit=8)
            all_incoming.extend(hn_jobs)
        except Exception as e:
            logger.warning(f"HN feed error: {e}")

        if len(all_incoming) < 5:
            all_incoming.extend(get_mock_jobs())

    for job in all_incoming:
        if job.id not in JOBS_STORE:
            JOBS_STORE[job.id] = job
            eval_res = evaluate_job_fit(job, CURRENT_PROFILE)
            EVALUATIONS_STORE[job.id] = eval_res
            discovered_count += 1
            await SSE_QUEUE.put({
                "event": "job_discovered",
                "data": json.dumps({"title": job.title, "company": job.company, "score": eval_res.score})
            })

    # Auto-precompile for top items in background
    generate_executive_briefing(list(JOBS_STORE.values()), CURRENT_PROFILE, PACKAGES_STORE, top_limit=3)

    return {"status": "success", "discovered_new": discovered_count, "total_stored": len(JOBS_STORE)}


class URLParseRequest(BaseModel):
    url: str


@app.post("/api/jobs/parse-url")
def parse_direct_job_url(req: URLParseRequest):
    job = parse_job_url(req.url)
    if not job:
        raise HTTPException(status_code=400, detail="Could not extract job details from provided URL.")
    
    JOBS_STORE[job.id] = job
    eval_res = evaluate_job_fit(job, CURRENT_PROFILE)
    EVALUATIONS_STORE[job.id] = eval_res
    return {
        "status": "success",
        "job": job.model_dump(),
        "evaluation": eval_res.model_dump(),
    }


# ── Triage & Application Actions ──────────────────────────────────────────────

class TriageActionRequest(BaseModel):
    status: TriageStatus


@app.post("/api/jobs/{job_id}/triage")
def triage_job(job_id: str, req: TriageActionRequest):
    if job_id not in JOBS_STORE:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = JOBS_STORE[job_id]
    job.triage_status = req.status
    logger.info(f"[API] Job {job_id} triage updated to: {req.status}")
    return {"status": "success", "job_id": job_id, "new_status": req.status}


@app.post("/api/jobs/{job_id}/apply")
def mark_job_applied(job_id: str):
    """Marks role as applied and initiates 5-day Response Radar."""
    if job_id not in JOBS_STORE:
        raise HTTPException(status_code=404, detail="Job not found")

    job = JOBS_STORE[job_id]
    job.triage_status = TriageStatus.AWAITING_REPLY

    package = PACKAGES_STORE.get(job_id)
    pitch_text = package.direct_pitch_letter if package else None

    app_record = ApplicationRecord(
        job_id=job.id,
        company=job.company,
        title=job.title,
        applied_at=datetime.now(timezone.utc),
        days_since_applied=0,
        status=TriageStatus.AWAITING_REPLY,
        follow_up_due=False,
        follow_up_count=0,
        direct_pitch_letter=pitch_text,
    )
    APPLICATIONS_STORE[job_id] = app_record
    logger.info(f"[API] Application logged for {job.company} — Response Radar active")
    return {"status": "success", "application": app_record.model_dump()}


# ── Application Response Radar & Pipeline ─────────────────────────────────────

@app.get("/api/pipeline")
def get_pipeline():
    """Returns active application pipeline with response radar & follow-up due flags."""
    pipeline_items = []
    now = datetime.now(timezone.utc)
    
    for job_id, app_rec in APPLICATIONS_STORE.items():
        job = JOBS_STORE.get(job_id)
        app_dt = app_rec.applied_at if app_rec.applied_at.tzinfo else app_rec.applied_at.replace(tzinfo=timezone.utc)
        days_elapsed = (now - app_dt).days
        app_rec.days_since_applied = max(0, days_elapsed)
        
        # Follow-up due after 5 days if still awaiting reply
        if days_elapsed >= 5 and app_rec.status in (TriageStatus.AWAITING_REPLY, TriageStatus.FOLLOW_UP_DUE):
            app_rec.follow_up_due = True
            app_rec.status = TriageStatus.FOLLOW_UP_DUE
            if job:
                job.triage_status = TriageStatus.FOLLOW_UP_DUE
        
        eval_res = EVALUATIONS_STORE.get(job_id)
        pipeline_items.append({
            "application": app_rec.model_dump(),
            "job": job.model_dump() if job else None,
            "evaluation": eval_res.model_dump() if eval_res else None,
            "has_package": job_id in PACKAGES_STORE,
        })

    # Sort: follow-up due first, then recent applied
    pipeline_items.sort(key=lambda x: (x["application"]["follow_up_due"], x["application"]["days_since_applied"]), reverse=True)
    return {
        "total_active": len(pipeline_items),
        "follow_up_due_count": sum(1 for p in pipeline_items if p["application"]["follow_up_due"]),
        "applications": pipeline_items,
    }


@app.post("/api/jobs/{job_id}/generate-followup")
def generate_followup(job_id: str):
    """Generates a 2-sentence value-add follow-up draft."""
    job = JOBS_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    app_rec = APPLICATIONS_STORE.get(job_id)
    days = app_rec.days_since_applied if app_rec else 5

    draft = generate_value_add_followup(job, CURRENT_PROFILE, days_since=days)
    return {"status": "success", "followup_draft": draft.model_dump()}


@app.post("/api/jobs/{job_id}/send-followup")
def record_followup_sent(job_id: str):
    """Records that a follow-up was dispatched, resetting the follow-up due flag."""
    app_rec = APPLICATIONS_STORE.get(job_id)
    if not app_rec:
        raise HTTPException(status_code=404, detail="Application record not found")

    app_rec.follow_up_count += 1
    app_rec.last_follow_up_at = datetime.now(timezone.utc)
    app_rec.follow_up_due = False
    app_rec.status = TriageStatus.AWAITING_REPLY

    job = JOBS_STORE.get(job_id)
    if job:
        job.triage_status = TriageStatus.AWAITING_REPLY

    logger.info(f"[API] Follow-up #{app_rec.follow_up_count} logged for {app_rec.company}")
    return {"status": "success", "application": app_rec.model_dump()}


# ── Drafter -> Reviewer -> PDF Compiler Pipeline ──────────────────────────────

@app.post("/api/jobs/{job_id}/prepare-package")
def prepare_package(job_id: str):
    if job_id not in JOBS_STORE:
        raise HTTPException(status_code=404, detail="Job not found")

    job = JOBS_STORE[job_id]
    
    # 1. Drafter Agent
    package = draft_tailored_package(job, CURRENT_PROFILE)

    # 2. Reviewer / ATS Auditor Agent
    audit_res = audit_tailored_package(package, job, CURRENT_PROFILE)
    package.audit_result = audit_res

    # 3. PDF Compiler Engine (50ms ReportLab ATS generation)
    pdf_filename = compile_ats_resume_pdf(package, CURRENT_PROFILE)
    package.pdf_filename = pdf_filename

    PACKAGES_STORE[job_id] = package
    job.triage_status = TriageStatus.PACKAGE_PREPARED

    return {
        "status": "success",
        "package": package.model_dump(),
        "pdf_url": f"/api/jobs/{job_id}/pdf",
    }


@app.get("/api/jobs/{job_id}/pdf")
def download_resume_pdf(job_id: str):
    package = PACKAGES_STORE.get(job_id)
    if not package or not package.pdf_filename:
        raise HTTPException(status_code=404, detail="No compiled PDF package found for this job.")
    
    pdf_path = OUTPUT_DIR / package.pdf_filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file missing on server disk.")

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=package.pdf_filename
    )


# ── Mock Interview Simulator ──────────────────────────────────────────────────

@app.post("/api/interview/{job_id}/start")
def start_interview_session(job_id: str):
    if job_id not in JOBS_STORE:
        raise HTTPException(status_code=404, detail="Job not found")

    job = JOBS_STORE[job_id]
    session = generate_mock_interview_questions(job, CURRENT_PROFILE)
    INTERVIEWS_STORE[session.session_id] = session

    return {
        "status": "success",
        "session": session.model_dump(),
    }


class AnswerSubmission(BaseModel):
    session_id: str
    question_id: int
    user_answer: str


@app.post("/api/interview/evaluate")
def submit_interview_answer(sub: AnswerSubmission):
    session = INTERVIEWS_STORE.get(sub.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    question = next((q for q in session.questions if q.question_id == sub.question_id), None)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in this session.")

    job = JOBS_STORE.get(session.job_id)
    if not job:
        job = get_mock_jobs()[0]

    evaluation = evaluate_interview_answer(question, sub.user_answer, job)

    existing_idx = next((i for i, e in enumerate(session.evaluations) if e.question_id == sub.question_id), None)
    if existing_idx is not None:
        session.evaluations[existing_idx] = evaluation
    else:
        session.evaluations.append(evaluation)

    if session.evaluations:
        session.overall_score = int(sum(e.score for e in session.evaluations) / len(session.evaluations))

    return {
        "status": "success",
        "evaluation": evaluation.model_dump(),
        "overall_score": session.overall_score,
    }


# ── SSE Live Stream ───────────────────────────────────────────────────────────

@app.get("/api/events")
async def sse_events():
    async def event_generator():
        while True:
            try:
                event_data = await asyncio.wait_for(SSE_QUEUE.get(), timeout=20.0)
                yield {
                    "event": event_data.get("event", "message"),
                    "data": event_data.get("data", "{}"),
                }
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "keep-alive"}

    return EventSourceResponse(event_generator())


# ── Static UI Mount ───────────────────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>RolePointer API is running. UI not found.</h1>"
