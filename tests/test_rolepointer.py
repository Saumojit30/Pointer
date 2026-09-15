"""
RolePointer — Comprehensive Test Suite
Tests Model Config, Feed Parsers, Fit Evaluator & Guardrails,
Drafter & ATS Reviewer Pipeline, PDF Compiler, Interview Simulator,
Executive Daily Briefing Engine, Response Radar & Follow-Up Generator,
SQLite WAL Database Persistence Layer, Resume Importer, RFC 5322 EML Exporter,
and all FastAPI REST Endpoints.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from rolepointer.api.main import app, JOBS_STORE, CURRENT_PROFILE, PACKAGES_STORE
from rolepointer.models.schemas import (
    JobListing, UserProfile, WorkplaceType, ExperienceLevel, TriageStatus,
    ApplicationRecord, TailoredPackage, ReviewAuditResult, MockInterviewSession,
    MockInterviewQuestion, MockInterviewEvaluation
)
from rolepointer.feeds.mock_feeds import get_mock_jobs
from rolepointer.feeds.location_feeds import filter_by_location
from rolepointer.agents.fit_evaluator import evaluate_job_fit
from rolepointer.agents.drafter import draft_tailored_package
from rolepointer.agents.reviewer import audit_tailored_package
from rolepointer.agents.briefing_agent import generate_executive_briefing
from rolepointer.agents.followup_agent import generate_value_add_followup
from rolepointer.agents.importer_agent import import_profile_from_text, _heuristic_fallback_parse
from rolepointer.agents.email_exporter import generate_eml_file, generate_mailto_url
from rolepointer.agents.interview_agent import (
    generate_mock_interview_questions, evaluate_interview_answer
)
from rolepointer.compiler.pdf_engine import compile_ats_resume_pdf, OUTPUT_DIR
from rolepointer.core.model_config import get_strands_model
from rolepointer.db.repository import (
    init_db, save_job, get_all_jobs_with_evaluations,
    save_application, get_all_applications,
    save_tailored_package, get_all_tailored_packages,
    save_user_profile, get_user_profile,
    save_interview_session, get_interview_session
)


client = TestClient(app)


def test_model_config_initialization():
    model = get_strands_model()
    assert model is not None


def test_mock_feeds_generation():
    jobs = get_mock_jobs()
    assert len(jobs) >= 6
    assert any(j.workplace_type == WorkplaceType.REMOTE for j in jobs)
    assert any(j.country == "United States" for j in jobs)
    assert any(j.city == "Berlin" for j in jobs)


def test_location_filtering():
    jobs = get_mock_jobs()
    sf_jobs = filter_by_location(jobs, target_cities=["San Francisco"])
    assert len(sf_jobs) >= 1
    assert all("San Francisco" in (j.city or "") or j.city == "Remote" for j in sf_jobs)

    germany_jobs = filter_by_location(jobs, target_countries=["Germany"])
    assert len(germany_jobs) >= 1
    assert any("Germany" in (j.country or "") for j in germany_jobs)


def test_fit_evaluator_high_match():
    profile = UserProfile()
    jobs = get_mock_jobs()
    ai_job = next(j for j in jobs if j.id == "mock-job-01")
    
    eval_res = evaluate_job_fit(ai_job, profile)
    assert eval_res.score >= 85
    assert eval_res.match_tier in ("EXCELLENT", "STRONG")
    assert not eval_res.has_dealbreaker
    assert len(eval_res.matching_skills) >= 2


def test_fit_evaluator_dealbreaker_alert():
    profile = UserProfile()
    jobs = get_mock_jobs()
    crypto_job = next(j for j in jobs if j.id == "mock-job-06")

    eval_res = evaluate_job_fit(crypto_job, profile)
    assert eval_res.has_dealbreaker is True
    assert eval_res.score <= 40
    assert any("crypto" in alert.rule.lower() or "overtime" in alert.rule.lower() for alert in eval_res.dealbreaker_alerts)


def test_drafter_reviewer_pipeline():
    profile = UserProfile()
    jobs = get_mock_jobs()
    job = jobs[0]

    package = draft_tailored_package(job, profile)
    assert len(package.tailored_experience_bullets) >= 2
    assert len(package.direct_pitch_letter) > 50

    audit_res = audit_tailored_package(package, job, profile)
    assert audit_res.ats_score >= 80
    assert audit_res.passed is True


def test_pdf_compiler_instant_generation():
    profile = UserProfile()
    jobs = get_mock_jobs()
    job = jobs[0]

    package = draft_tailored_package(job, profile)
    pdf_filename = compile_ats_resume_pdf(package, profile)
    assert pdf_filename.endswith(".pdf")
    
    pdf_path = OUTPUT_DIR / pdf_filename
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000


def test_mock_interview_simulator():
    profile = UserProfile()
    jobs = get_mock_jobs()
    job = jobs[0]

    session = generate_mock_interview_questions(job, profile)
    assert len(session.questions) == 4
    assert any(q.category == "Technical Core" for q in session.questions)
    assert any(q.category == "System Design & Reliability" for q in session.questions)

    sample_ans = (
        "I led the migration of our legacy monolith to high-throughput async microservices using Python and FastAPI. "
        "By implementing Redis caching layers and optimizing PostgreSQL connection pools, we reduced p99 latency by 45% "
        "and scaled concurrency to 10M daily requests while maintaining 99.99% SLA."
    )
    evaluation = evaluate_interview_answer(session.questions[0], sample_ans, job)
    assert evaluation.score >= 70
    assert len(evaluation.strengths) >= 1
    assert len(evaluation.suggested_ideal_answer) > 20


def test_executive_morning_briefing_engine():
    jobs = get_mock_jobs()
    profile = UserProfile()
    packages_store = {}

    briefing, precompiled = generate_executive_briefing(jobs, profile, packages_store, top_limit=3)
    assert len(briefing.top_opportunities) == 3
    assert len(precompiled) == 3
    assert all(ev.score >= 70 for ev in briefing.top_evaluations)
    assert "Good morning" in briefing.executive_summary
    assert briefing.qualified_count >= 3


def test_value_add_followup_agent():
    jobs = get_mock_jobs()
    profile = UserProfile()
    job = jobs[1]

    draft = generate_value_add_followup(job, profile, days_since=6)
    assert draft.job_id == job.id
    assert draft.company == job.company
    assert "Re:" in draft.subject
    assert "benchmark" in draft.body.lower() or "throughput" in draft.body.lower() or "latency" in draft.body.lower()
    assert len(draft.talking_point) > 10


def test_sqlite_persistence_and_repository(tmp_path):
    init_db()
    
    # 1. Save Job & Evaluation
    jobs = get_mock_jobs()
    job = jobs[0]
    profile = UserProfile()
    ev = evaluate_job_fit(job, profile)
    save_job(job, ev)

    persisted_jobs = get_all_jobs_with_evaluations()
    assert len(persisted_jobs) >= 1
    matching = next((j for j, e in persisted_jobs if j.id == job.id), None)
    assert matching is not None
    assert matching.company == job.company

    # 2. Save and Retrieve Application Record
    app_rec = ApplicationRecord(
        job_id=job.id,
        company=job.company,
        title=job.title,
        applied_at=datetime.now(timezone.utc),
        days_since_applied=0,
        status=TriageStatus.AWAITING_REPLY,
    )
    save_application(app_rec)
    all_apps = get_all_applications()
    assert job.id in all_apps
    assert all_apps[job.id].company == job.company

    # 3. Save and Retrieve User Profile
    save_user_profile(profile)
    p_ret = get_user_profile(profile.id)
    assert p_ret is not None
    assert p_ret.name == profile.name


def test_profile_importer_agent():
    sample_resume = """Alex Morgan
Senior Software Engineer
Email: alex.morgan@example.com
Phone: +1 (555) 234-5678
Location: San Francisco, CA

Summary: Senior Engineer with 6+ years building Python, FastAPI, and AWS distributed systems.
Skills: Python, FastAPI, PostgreSQL, AWS, Docker, Kubernetes, PyTorch, React, Redis.
Looking for Senior Backend Engineer or AI Systems Engineer roles.
Dealbreakers: No unpaid overtime, no crypto gambling.
"""
    profile = _heuristic_fallback_parse(sample_resume)
    assert profile.name == "Alex Morgan"
    assert profile.email == "alex.morgan@example.com"
    assert "Python" in profile.skills
    assert "FastAPI" in profile.skills
    assert "Backend" in profile.target_domains
    assert any("overtime" in d.lower() for d in profile.dealbreakers)


def test_email_exporter_eml_and_mailto(tmp_path):
    eml_file = generate_eml_file(
        company="CognitiveFlow AI",
        role_title="Senior AI Platform Engineer",
        pitch_body="Hi CognitiveFlow Team,\n\nI built high-throughput AI microservices...",
        candidate_name="Alex Morgan",
        candidate_email="alex.morgan@example.com",
        output_dir=tmp_path,
    )
    eml_path = tmp_path / eml_file
    assert eml_path.exists()
    content = eml_path.read_text(encoding="utf-8")
    assert "Subject: Application: Senior AI Platform Engineer" in content
    assert "From: Alex Morgan <alex.morgan@example.com>" in content

    mailto = generate_mailto_url(
        company="CognitiveFlow AI",
        role_title="Senior AI Platform Engineer",
        pitch_body="Hi Team, excited to apply.",
        candidate_name="Alex Morgan",
    )
    assert mailto.startswith("mailto:")
    assert "CognitiveFlow" in mailto


def test_api_list_jobs():
    response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert "jobs" in data


def test_api_executive_briefing_endpoint():
    response = client.get("/api/briefing")
    assert response.status_code == 200
    briefing = response.json()
    assert "top_opportunities" in briefing
    assert len(briefing["top_opportunities"]) <= 3
    assert "precompiled_packages" in briefing
    assert len(briefing["precompiled_packages"]) <= 3
    assert "Good morning" in briefing["executive_summary"]


def test_api_pipeline_and_response_radar():
    jobs = get_mock_jobs()
    job_id = jobs[0].id

    # 1. Apply to job
    apply_res = client.post(f"/api/jobs/{job_id}/apply")
    assert apply_res.status_code == 200
    app_rec = apply_res.json()["application"]
    assert app_rec["status"] == "awaiting_reply"
    assert app_rec["days_since_applied"] == 0

    # 2. Get Pipeline
    pipe_res = client.get("/api/pipeline")
    assert pipe_res.status_code == 200
    pipeline = pipe_res.json()
    assert pipeline["total_active"] >= 1
    assert "follow_up_due_count" in pipeline

    # 3. Generate Follow-Up
    follow_res = client.post(f"/api/jobs/{job_id}/generate-followup")
    assert follow_res.status_code == 200
    draft = follow_res.json()["followup_draft"]
    assert draft["company"] == jobs[0].company
    assert "Re:" in draft["subject"]

    # 4. Record Follow-Up Sent
    send_res = client.post(f"/api/jobs/{job_id}/send-followup")
    assert send_res.status_code == 200
    updated_rec = send_res.json()["application"]
    assert updated_rec["follow_up_count"] == 1
    assert updated_rec["follow_up_due"] is False


def test_api_prepare_package_and_download_pdf():
    jobs = get_mock_jobs()
    job_id = jobs[0].id

    res = client.post(f"/api/jobs/{job_id}/prepare-package")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "package" in data
    assert "pdf_url" in data

    pdf_res = client.get(f"/api/jobs/{job_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert len(pdf_res.content) > 1000


def test_api_eml_and_mailto_endpoints():
    jobs = get_mock_jobs()
    job_id = jobs[0].id

    # Mailto Link
    m_res = client.get(f"/api/jobs/{job_id}/mailto")
    assert m_res.status_code == 200
    assert "mailto:" in m_res.json()["mailto_url"]

    # EML Download
    e_res = client.get(f"/api/jobs/{job_id}/eml")
    assert e_res.status_code == 200
    assert "message/rfc822" in e_res.headers["content-type"]
    assert len(e_res.content) > 50


def test_api_profile_import_endpoint():
    resume_text = "Jane Doe\nLead AI Architect\njane.doe@example.com\nSkills: Python, PyTorch, FastAPI, AWS, Docker."
    res = client.post("/api/profile/import", json={"raw_text": resume_text})
    assert res.status_code == 200
    profile = res.json()
    assert profile["email"] == "jane.doe@example.com"
    assert "Python" in profile["skills"]
