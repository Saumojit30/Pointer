"""
RolePointer — FastAPI Application & Orchestration Gateway
REST Endpoints, Real-Time SSE Streams, Triage & Mock Interview Handlers.
"""
from __future__ import annotations

import asyncio
import json
import os
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
    TriageStatus, WorkplaceType, FeedFilterQuery
)
from rolepointer.feeds.mock_feeds import get_mock_jobs
from rolepointer.feeds.remote_feeds import fetch_jobicy_jobs, fetch_remoteok_jobs
from rolepointer.feeds.location_feeds import fetch_arbeitnow_jobs, filter_by_location
from rolepointer.feeds.hn_hiring_feed import fetch_hn_hiring_jobs
from rolepointer.feeds.url_parser import parse_job_url
from rolepointer.agents.fit_evaluator import evaluate_job_fit
from rolepointer.agents.drafter import draft_tailored_package
from rolepointer.agents.reviewer import audit_tailored_package
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

# ── In-Memory Repository (with instant startup & SQLite sync) ──────────────────
CURRENT_PROFILE: UserProfile = UserProfile()
JOBS_STORE: Dict[str, JobListing] = {}
EVALUATIONS_STORE: Dict[str, FitEvaluation] = {}
PACKAGES_STORE: Dict[str, TailoredPackage] = {}
INTERVIEWS_STORE: Dict[str, MockInterviewSession] = {}
SSE_QUEUE: asyncio.Queue = asyncio.Queue()


def _populate_initial_data():
    """Seed with mock jobs evaluated against user profile."""
    for job in get_mock_jobs():
        JOBS_STORE[job.id] = job
        eval_res = evaluate_job_fit(job, CURRENT_PROFILE)
        EVALUATIONS_STORE[job.id] = eval_res


_populate_initial_data()


# ── Profile Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/profile", response_model=UserProfile)
def get_profile():
    return CURRENT_PROFILE


@app.post("/api/profile", response_model=UserProfile)
def update_profile(profile: UserProfile):
    global CURRENT_PROFILE
    CURRENT_PROFILE = profile
    # Re-evaluate stored jobs with updated preferences
    for job_id, job in JOBS_STORE.items():
        EVALUATIONS_STORE[job_id] = evaluate_job_fit(job, CURRENT_PROFILE)
    logger.info("[API] Profile updated and jobs re-evaluated")
    return CURRENT_PROFILE


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

        # Filters
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

    # Sort descending by score
    results.sort(key=lambda x: (x["evaluation"]["score"] if x["evaluation"] else 0), reverse=True)
    return {"total": len(results), "jobs": results}


@app.post("/api/jobs/discover")
async def trigger_discovery():
    """Discovers jobs from live feeds and mock fixtures concurrently."""
    discovered_count = 0
    all_incoming: List[JobListing] = []

    # 1. Fetch from connectors
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

        # Always ensure mock listings are present if feeds yield low count
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


# ── Triage Guardrail ──────────────────────────────────────────────────────────

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

    # Save to store & update job status
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
        raise HTTPException(status_code=404, detail="No compiled PDF package found for this job. Click 'Prepare Package' first.")
    
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

    # Upsert evaluation into session
    existing_idx = next((i for i, e in enumerate(session.evaluations) if e.question_id == sub.question_id), None)
    if existing_idx is not None:
        session.evaluations[existing_idx] = evaluation
    else:
        session.evaluations.append(evaluation)

    # Compute overall score
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
