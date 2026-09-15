"""
RolePointer — FastAPI Application & Orchestration Gateway
REST Endpoints, Real-Time SSE Streams, Executive Morning Briefing,
Response Radar with Value-Add Follow-Up Generator, Resume Importer,
RFC 5322 EML Exporter, and SQLite WAL Persistence Synchronization.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends, Request
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
from rolepointer.agents.importer_agent import import_profile_from_text
from rolepointer.agents.email_exporter import generate_eml_file, generate_mailto_url, OUTPUT_DIR as EML_DIR
from rolepointer.agents.interview_agent import (
    generate_mock_interview_questions, evaluate_interview_answer
)
from rolepointer.compiler.pdf_engine import compile_ats_resume_pdf, OUTPUT_DIR
from rolepointer.db.repository import (
    init_db, save_job, get_all_jobs_with_evaluations,
    save_application, get_all_applications,
    save_tailored_package, get_all_tailored_packages,
    save_user_profile, get_user_profile,
    save_interview_session, get_interview_session
)
from rolepointer.scheduler.poller import run_discovery_cycle, background_poller_loop

# ── In-Memory Repository (Synchronized with SQLite WAL) ───────────────────────
CURRENT_PROFILE: UserProfile = UserProfile()
JOBS_STORE: Dict[str, JobListing] = {}
EVALUATIONS_STORE: Dict[str, FitEvaluation] = {}
PACKAGES_STORE: Dict[str, TailoredPackage] = {}
INTERVIEWS_STORE: Dict[str, MockInterviewSession] = {}
APPLICATIONS_STORE: Dict[str, ApplicationRecord] = {}
SSE_QUEUE: asyncio.Queue = asyncio.Queue()
POLLER_TASK: Optional[asyncio.Task] = None


def _hydrate_or_seed_db():
    """Initializes SQLite schema and hydrates memory cache or seeds initial records."""
    global CURRENT_PROFILE, JOBS_STORE, EVALUATIONS_STORE, PACKAGES_STORE, APPLICATIONS_STORE
    init_db()

    # 1. Profile Hydration
    persisted_profile = get_user_profile()
    if persisted_profile:
        CURRENT_PROFILE = persisted_profile
        logger.info(f"[DB] Hydrated User Profile: {CURRENT_PROFILE.name}")
    else:
        save_user_profile(CURRENT_PROFILE)
        logger.info(f"[DB] Seeded default User Profile: {CURRENT_PROFILE.name}")

    # 2. Jobs & Evaluations Hydration
    persisted_jobs = get_all_jobs_with_evaluations()
    if persisted_jobs:
        for job, eval_res in persisted_jobs:
            JOBS_STORE[job.id] = job
            if eval_res:
                EVALUATIONS_STORE[job.id] = eval_res
        logger.info(f"[DB] Hydrated {len(JOBS_STORE)} jobs from database.")
    else:
        # Seed mock jobs
        for job in get_mock_jobs():
            JOBS_STORE[job.id] = job
            eval_res = evaluate_job_fit(job, CURRENT_PROFILE)
            EVALUATIONS_STORE[job.id] = eval_res
            save_job(job, eval_res)
        logger.info(f"[DB] Seeded and persisted {len(JOBS_STORE)} mock jobs.")

    # 3. Applications Hydration
    persisted_apps = get_all_applications()
    if persisted_apps:
        APPLICATIONS_STORE = persisted_apps
        logger.info(f"[DB] Hydrated {len(APPLICATIONS_STORE)} active applications from database.")
    else:
        # Seed 1 active application in Awaiting Reply (Day 2)
        job1 = JOBS_STORE.get("mock-job-01")
        if job1:
            job1.triage_status = TriageStatus.AWAITING_REPLY
            app1 = ApplicationRecord(
                job_id=job1.id,
                company=job1.company,
                title=job1.title,
                applied_at=datetime.now(timezone.utc) - timedelta(days=2),
                days_since_applied=2,
                status=TriageStatus.AWAITING_REPLY,
                follow_up_due=False,
                follow_up_count=0,
            )
            APPLICATIONS_STORE[job1.id] = app1
            save_application(app1)
            save_job(job1, EVALUATIONS_STORE.get(job1.id))

        # Seed 1 active application in Follow-Up Due (Day 6 without reply)
        job2 = JOBS_STORE.get("mock-job-02")
        if job2:
            job2.triage_status = TriageStatus.FOLLOW_UP_DUE
            app2 = ApplicationRecord(
                job_id=job2.id,
                company=job2.company,
                title=job2.title,
                applied_at=datetime.now(timezone.utc) - timedelta(days=6),
                days_since_applied=6,
                status=TriageStatus.FOLLOW_UP_DUE,
                follow_up_due=True,
                follow_up_count=0,
            )
            APPLICATIONS_STORE[job2.id] = app2
            save_application(app2)
            save_job(job2, EVALUATIONS_STORE.get(job2.id))

    # 4. Tailored Packages Hydration
    persisted_pkgs = get_all_tailored_packages()
    if persisted_pkgs:
        PACKAGES_STORE = persisted_pkgs
        logger.info(f"[DB] Hydrated {len(PACKAGES_STORE)} tailored packages from database.")


_hydrate_or_seed_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: hydrate database tables and seed initial state if empty
    _hydrate_or_seed_db()
    global POLLER_TASK
    if os.getenv("ENABLE_BACKGROUND_POLLER", "false").lower() == "true":
        POLLER_TASK = asyncio.create_task(
            background_poller_loop(
                profile_getter=lambda: CURRENT_PROFILE,
                jobs_store=JOBS_STORE,
                evaluations_store=EVALUATIONS_STORE,
                sse_queue=SSE_QUEUE,
                interval_seconds=1800,
            )
        )
        logger.info("[Lifespan] Background poller daemon initialized.")
    yield
    # Shutdown
    if POLLER_TASK and not POLLER_TASK.done():
        POLLER_TASK.cancel()
        try:
            await POLLER_TASK
        except asyncio.CancelledError:
            pass
        logger.info("[Lifespan] Background poller daemon shut down.")


app = FastAPI(
    title="RolePointer API",
    description="Autonomous Job Discovery, Guardrail Triage & Tailored Career Pipeline",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Profile Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/profile", response_model=UserProfile)
def get_profile():
    return CURRENT_PROFILE


@app.post("/api/profile", response_model=UserProfile)
def update_profile(profile: UserProfile):
    global CURRENT_PROFILE
    CURRENT_PROFILE = profile
    save_user_profile(CURRENT_PROFILE)
    logger.info(f"[API] Profile updated & persisted for: {profile.name}")
    return CURRENT_PROFILE


class ImportProfileRequest(BaseModel):
    raw_text: str


@app.post("/api/profile/import", response_model=UserProfile)
def import_profile(req: ImportProfileRequest):
    """Parses raw resume/LinkedIn text and updates candidate profile."""
    global CURRENT_PROFILE
    new_profile = import_profile_from_text(req.raw_text)
    CURRENT_PROFILE = new_profile
    save_user_profile(CURRENT_PROFILE)
    
    # Re-evaluate in-memory jobs with new profile guardrails
    for job_id, job in JOBS_STORE.items():
        ev = evaluate_job_fit(job, CURRENT_PROFILE)
        EVALUATIONS_STORE[job_id] = ev
        save_job(job, ev)

    logger.info(f"[API] Imported and persisted candidate profile for: {CURRENT_PROFILE.name}")
    return CURRENT_PROFILE


# ── Job Feeds & Discovery Endpoints ───────────────────────────────────────────

@app.get("/api/jobs")
def list_jobs(
    domain: Optional[str] = Query(None),
    workplace_type: Optional[WorkplaceType] = Query(None),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    status: Optional[TriageStatus] = Query(None),
):
    """Returns stored jobs with fit evaluations and active triage status."""
    results = []
    for job_id, job in JOBS_STORE.items():
        if domain and job.domain.lower() != domain.lower():
            continue
        if workplace_type and job.workplace_type != workplace_type:
            continue
        if country and job.country and country.lower() not in job.country.lower():
            continue
        if city and job.city and city.lower() not in job.city.lower():
            continue
        if status and job.triage_status != status:
            continue

        eval_res = EVALUATIONS_STORE.get(job_id)
        if min_score is not None and eval_res and eval_res.score < min_score:
            continue

        results.append({
            "job": job.model_dump(),
            "evaluation": eval_res.model_dump() if eval_res else None,
            "has_package": job_id in PACKAGES_STORE,
            "is_applied": job_id in APPLICATIONS_STORE,
        })

    # Sort descending by match score
    results.sort(key=lambda x: (x["evaluation"]["score"] if x["evaluation"] else 0), reverse=True)
    return {
        "total": len(results),
        "jobs": results,
        "results": results,
    }


@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str):
    if job_id not in JOBS_STORE:
        raise HTTPException(status_code=404, detail="Job not found")
    job = JOBS_STORE[job_id]
    eval_res = EVALUATIONS_STORE.get(job_id)
    package = PACKAGES_STORE.get(job_id)
    app_rec = APPLICATIONS_STORE.get(job_id)

    return {
        "job": job.model_dump(),
        "evaluation": eval_res.model_dump() if eval_res else None,
        "package": package.model_dump() if package else None,
        "application": app_rec.model_dump() if app_rec else None,
    }


class URLParseRequest(BaseModel):
    url: str


@app.post("/api/jobs/parse-url")
def parse_and_add_job_url(req: URLParseRequest):
    """Scrapes a single job posting URL and adds it to the pipeline."""
    job = parse_job_url(req.url)
    JOBS_STORE[job.id] = job
    eval_res = evaluate_job_fit(job, CURRENT_PROFILE)
    EVALUATIONS_STORE[job.id] = eval_res
    save_job(job, eval_res)
    return {
        "status": "success",
        "job": job.model_dump(),
        "evaluation": eval_res.model_dump(),
    }


# ── Executive Morning Briefing ────────────────────────────────────────────────

@app.get("/api/briefing", response_model=ExecutiveBriefing)
def get_executive_briefing():
    """Returns today's curated Top 3 high-fit opportunities with pre-compiled packages."""
    briefing, precompiled = generate_executive_briefing(
        jobs=list(JOBS_STORE.values()),
        profile=CURRENT_PROFILE,
        packages_store=PACKAGES_STORE,
        top_limit=3,
    )
    for pkg in precompiled:
        save_tailored_package(pkg)
    return briefing


# ── Triage & Application Actions ──────────────────────────────────────────────

class TriageActionRequest(BaseModel):
    status: TriageStatus


@app.post("/api/jobs/{job_id}/triage")
def triage_job(job_id: str, req: TriageActionRequest):
    if job_id not in JOBS_STORE:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = JOBS_STORE[job_id]
    job.triage_status = req.status
    save_job(job, EVALUATIONS_STORE.get(job_id))
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
    save_application(app_record)
    save_job(job, EVALUATIONS_STORE.get(job_id))
    logger.info(f"[API] Application logged and persisted for {job.company} — Response Radar active")
    return {"status": "success", "application": app_record.model_dump()}


# ── Application Response Radar & Pipeline ─────────────────────────────────────

@app.get("/api/pipeline")
def get_pipeline():
    """Returns active application pipeline with response radar & follow-up due flags."""
    pipeline_items = []
    now = datetime.now(timezone.utc)
    
    for job_id, app_rec in list(APPLICATIONS_STORE.items()):
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
                save_job(job, EVALUATIONS_STORE.get(job_id))
            save_application(app_rec)
        
        eval_res = EVALUATIONS_STORE.get(job_id)
        pipeline_items.append({
            "application": app_rec.model_dump(),
            "job": job.model_dump() if job else None,
            "evaluation": eval_res.model_dump() if eval_res else None,
            "has_package": job_id in PACKAGES_STORE,
        })

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
        save_job(job, EVALUATIONS_STORE.get(job_id))

    save_application(app_rec)
    logger.info(f"[API] Follow-up #{app_rec.follow_up_count} logged and persisted for {app_rec.company}")
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

    save_tailored_package(package)
    save_job(job, EVALUATIONS_STORE.get(job_id))

    return {
        "status": "success",
        "package": package.model_dump(),
        "pdf_url": f"/api/jobs/{job_id}/pdf",
        "eml_url": f"/api/jobs/{job_id}/eml",
    }


@app.get("/api/jobs/{job_id}/pdf")
def download_resume_pdf(job_id: str):
    package = PACKAGES_STORE.get(job_id)
    if not package or not package.pdf_filename:
        raise HTTPException(status_code=404, detail="No compiled PDF package found for this job.")
    
    pdf_path = OUTPUT_DIR / package.pdf_filename
    if not pdf_path.exists():
        compile_ats_resume_pdf(package, CURRENT_PROFILE)
    
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=package.pdf_filename,
    )


# ── RFC 5322 EML & Mailto Deep Link Endpoints ─────────────────────────────────

@app.get("/api/jobs/{job_id}/eml")
def download_pitch_eml(job_id: str):
    """Generates and downloads an RFC 5322 .eml file for native mail clients."""
    job = JOBS_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    package = PACKAGES_STORE.get(job_id)
    pitch_text = package.direct_pitch_letter if package else f"Hi {job.company} Team,\n\nI would love to connect regarding the {job.title} position."

    eml_name = generate_eml_file(
        company=job.company,
        role_title=job.title,
        pitch_body=pitch_text,
        candidate_name=CURRENT_PROFILE.name,
        candidate_email=CURRENT_PROFILE.email,
        output_dir=EML_DIR,
    )
    eml_path = EML_DIR / eml_name

    return FileResponse(
        path=str(eml_path),
        media_type="message/rfc822",
        filename=eml_name,
    )


@app.get("/api/jobs/{job_id}/mailto")
def get_mailto_link(job_id: str):
    """Returns a pre-formatted, URL-safe mailto: link for 1-click dispatch."""
    job = JOBS_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    package = PACKAGES_STORE.get(job_id)
    pitch_text = package.direct_pitch_letter if package else f"Hi {job.company} Team,\n\nI would love to connect regarding the {job.title} position."

    link = generate_mailto_url(
        company=job.company,
        role_title=job.title,
        pitch_body=pitch_text,
        candidate_name=CURRENT_PROFILE.name,
    )
    return {"status": "success", "mailto_url": link}


# ── Interactive Mock Interview Endpoints ──────────────────────────────────────

@app.post("/api/interview/{job_id}/start")
def start_interview_session(job_id: str):
    """Initializes a 4-question mock interview session."""
    job = JOBS_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    questions = generate_mock_interview_questions(job, CURRENT_PROFILE)
    session = MockInterviewSession(
        job_id=job.id,
        company=job.company,
        role=job.title,
        questions=questions,
        evaluations=[],
    )
    INTERVIEWS_STORE[session.session_id] = session
    save_interview_session(session)
    logger.info(f"[API] Mock interview session started for {job.company}: {session.session_id}")
    return {"status": "success", "session": session.model_dump()}


class InterviewAnswerSubmission(BaseModel):
    question_id: int
    user_answer: str


@app.post("/api/interview/{session_id}/evaluate")
def submit_interview_answer(session_id: str, sub: InterviewAnswerSubmission):
    """Evaluates candidate answer and updates overall score."""
    session = INTERVIEWS_STORE.get(session_id)
    if not session:
        session = get_interview_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")
        INTERVIEWS_STORE[session_id] = session

    target_q = next((q for q in session.questions if q.question_id == sub.question_id), None)
    if not target_q:
        raise HTTPException(status_code=404, detail=f"Question #{sub.question_id} not found in session")

    evaluation = evaluate_interview_answer(target_q, sub.user_answer, CURRENT_PROFILE)
    session.evaluations = [e for e in session.evaluations if e.question_id != sub.question_id]
    session.evaluations.append(evaluation)

    # Compute running overall score
    if session.evaluations:
        session.overall_score = int(sum(e.score for e in session.evaluations) / len(session.evaluations))

    save_interview_session(session)
    logger.info(f"[API] Evaluated question #{sub.question_id} (Score: {evaluation.score}/100)")
    return {
        "status": "success",
        "evaluation": evaluation.model_dump(),
        "overall_score": session.overall_score,
        "completed_count": len(session.evaluations),
        "total_questions": len(session.questions),
    }


# ── Background Scheduler Trigger ──────────────────────────────────────────────

@app.post("/api/scheduler/trigger")
async def trigger_scheduler_cycle():
    """Manually triggers a live discovery cycle across all external feeds."""
    new_jobs = await run_discovery_cycle(CURRENT_PROFILE, JOBS_STORE, EVALUATIONS_STORE, SSE_QUEUE)
    return {"status": "success", "new_jobs_discovered": new_jobs, "total_jobs": len(JOBS_STORE)}


# ── Real-Time SSE Stream Endpoint ─────────────────────────────────────────────

@app.get("/api/stream")
async def sse_event_stream(request: Request):
    """Server-Sent Events endpoint pushing real-time discovery and audit alerts."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                logger.info("[SSE] Client disconnected from event stream.")
                break
            try:
                msg = await asyncio.wait_for(SSE_QUEUE.get(), timeout=15.0)
                yield {
                    "event": msg.get("event", "update"),
                    "data": json.dumps(msg.get("data", {})),
                }
            except asyncio.TimeoutError:
                yield {
                    "event": "ping",
                    "data": json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}),
                }
            except Exception as e:
                logger.warning(f"[SSE] Stream generator error: {e}")
                break

    return EventSourceResponse(event_generator())


# ── Static UI Mounting ────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>RolePointer UI Loading...</h1>")
