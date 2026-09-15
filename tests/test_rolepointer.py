"""
RolePointer — Comprehensive Test Suite
Tests Model Config, Feed Parsers, Fit Evaluator & Dealbreakers,
Drafter & ATS Reviewer Pipeline, PDF Compiler, Interview Simulator, and FastAPI Endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from rolepointer.api.main import app, JOBS_STORE, CURRENT_PROFILE
from rolepointer.models.schemas import (
    JobListing, UserProfile, WorkplaceType, ExperienceLevel, TriageStatus
)
from rolepointer.feeds.mock_feeds import get_mock_jobs
from rolepointer.feeds.location_feeds import filter_by_location
from rolepointer.agents.fit_evaluator import evaluate_job_fit
from rolepointer.agents.drafter import draft_tailored_package
from rolepointer.agents.reviewer import audit_tailored_package
from rolepointer.agents.interview_agent import (
    generate_mock_interview_questions, evaluate_interview_answer
)
from rolepointer.compiler.pdf_engine import compile_ats_resume_pdf, OUTPUT_DIR
from rolepointer.core.model_config import get_strands_model


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
    assert eval_res.score >= 70
    assert eval_res.match_tier in ["STRONG", "EXCELLENT"]
    assert len(eval_res.matching_skills) > 0
    assert eval_res.has_dealbreaker is False


def test_fit_evaluator_dealbreaker_alert():
    profile = UserProfile()
    jobs = get_mock_jobs()
    crypto_job = next(j for j in jobs if j.id == "mock-job-06")
    
    eval_res = evaluate_job_fit(crypto_job, profile)
    assert eval_res.has_dealbreaker is True
    assert len(eval_res.dealbreaker_alerts) >= 1
    assert eval_res.score <= 55


def test_drafter_reviewer_pipeline():
    profile = UserProfile()
    jobs = get_mock_jobs()
    job = jobs[0]

    # Drafter
    package = draft_tailored_package(job, profile)
    assert len(package.tailored_experience_bullets) >= 4
    assert "Dear " in package.direct_pitch_letter
    assert package.company in package.direct_pitch_letter

    # Reviewer
    audit_res = audit_tailored_package(package, job, profile)
    assert audit_res.ats_score >= 70
    assert audit_res.passed is True
    assert len(audit_res.hallucination_flags) == 0


def test_pdf_compiler_instant_generation():
    profile = UserProfile()
    jobs = get_mock_jobs()
    job = jobs[0]

    package = draft_tailored_package(job, profile)
    pdf_filename = compile_ats_resume_pdf(package, profile)
    
    assert pdf_filename.endswith(".pdf")
    file_path = OUTPUT_DIR / pdf_filename
    assert file_path.exists()
    assert file_path.stat().st_size > 1000  # valid PDF bytes


def test_mock_interview_simulator():
    profile = UserProfile()
    jobs = get_mock_jobs()
    job = jobs[0]

    session = generate_mock_interview_questions(job, profile)
    assert len(session.questions) == 4
    
    q1 = session.questions[0]
    sample_answer = "I would use async Python with FastAPI and Redis caching to handle connection pools and optimize database query indexing to achieve sub-20ms p99 latency."
    
    eval_res = evaluate_interview_answer(q1, sample_answer, job)
    assert eval_res.score >= 70
    assert len(eval_res.strengths) > 0
    assert "exemplary" in eval_res.suggested_ideal_answer.lower()


def test_api_list_jobs():
    response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert "jobs" in data


def test_api_profile_get_and_update():
    response = client.get("/api/profile")
    assert response.status_code == 200
    current = response.json()
    assert "name" in current

    current["name"] = "Alex Test"
    update_res = client.post("/api/profile", json=current)
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Alex Test"


def test_api_prepare_package_and_download_pdf():
    jobs = get_mock_jobs()
    job_id = jobs[0].id

    # Prepare Package
    res = client.post(f"/api/jobs/{job_id}/prepare-package")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "package" in data
    assert "pdf_url" in data

    # Download PDF
    pdf_res = client.get(f"/api/jobs/{job_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert len(pdf_res.content) > 1000


def test_api_triage_flow():
    jobs = get_mock_jobs()
    job_id = jobs[0].id

    res = client.post(f"/api/jobs/{job_id}/triage", json={"status": "saved"})
    assert res.status_code == 200
    assert res.json()["new_status"] == "saved"
