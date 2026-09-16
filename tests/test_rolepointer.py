"""
RolePointer — Comprehensive Test Suite
Tests Model Config, Feed Parsers, Fit Evaluator & Guardrails,
Drafter & ATS Reviewer Pipeline, PDF Compiler, Interview Simulator,
Executive Daily Briefing Engine, Response Radar & Follow-Up Generator,
SQLite WAL Database Persistence Layer, Resume Importer, RFC 5322 EML Exporter,
Multi-Currency Compensation Normalizer, Anti-Ghost Heuristics,
Dead Link Pre-Flight Verifier, Work Authorization & Timezone Overlap,
High-Leverage Cold Angle Generator, and all FastAPI REST Endpoints.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from rolepointer.api.main import app, JOBS_STORE, CURRENT_PROFILE, PACKAGES_STORE
from rolepointer.models.schemas import (
    JobListing, UserProfile, WorkplaceType, ExperienceLevel, TriageStatus,
    ApplicationRecord, TailoredPackage, ReviewAuditResult, MockInterviewSession,
    MockInterviewQuestion, MockInterviewEvaluation, GhostRiskLevel, LinkStatus
)
from rolepointer.feeds.mock_feeds import get_mock_jobs
from rolepointer.feeds.location_feeds import filter_by_location
from rolepointer.feeds.salary_normalizer import normalize_compensation
from rolepointer.feeds.link_and_ghost_verifier import detect_ghost_job, verify_job_url
from rolepointer.feeds.work_auth_filter import evaluate_work_auth_and_timezone, compute_business_hours_overlap
from rolepointer.agents.fit_evaluator import evaluate_job_fit
from rolepointer.agents.drafter import draft_tailored_package
from rolepointer.agents.reviewer import audit_tailored_package
from rolepointer.agents.briefing_agent import generate_executive_briefing
from rolepointer.agents.followup_agent import generate_value_add_followup
from rolepointer.agents.importer_agent import import_profile_from_text, _heuristic_fallback_parse
from rolepointer.agents.cold_angle_agent import generate_high_leverage_cold_angle
from rolepointer.agents.email_exporter import generate_eml_file, generate_mailto_url
from rolepointer.agents.interview_agent import (
    generate_mock_interview_questions, evaluate_interview_answer
)
from rolepointer.compiler.pdf_engine import compile_ats_resume_pdf, OUTPUT_DIR
from rolepointer.core.model_config import (
    get_strands_model, BedrockStrandsModel, GCPGeminiStrandsModel, OllamaStrandsModel
)
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
    assert hasattr(model, "generate")

    # AWS Bedrock Adapter Test
    bedrock = BedrockStrandsModel(
        model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
        region_name="us-east-1",
    )
    assert bedrock.model_id == "anthropic.claude-3-5-haiku-20241022-v1:0"
    assert bedrock.region_name == "us-east-1"

    # GCP Gemini Adapter Test (AI Studio & Vertex AI modes)
    gcp_studio = GCPGeminiStrandsModel(
        model_id="gemini-2.5-flash",
        api_key="test-api-key",
    )
    assert gcp_studio.model_id == "gemini-2.5-flash"
    assert gcp_studio.api_key == "test-api-key"

    gcp_vertex = GCPGeminiStrandsModel(
        model_id="gemini-2.5-flash",
        project="test-gcp-project",
        location="us-central1",
        use_vertex_ai=True,
    )
    assert gcp_vertex.project == "test-gcp-project"
    assert gcp_vertex.location == "us-central1"
    assert gcp_vertex.use_vertex_ai is True


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


def test_salary_normalizer_multi_currency():
    # 1. USD Range
    usd_norm = normalize_compensation("$140k - $180k")
    assert usd_norm.annual_min_usd == 140000.0
    assert usd_norm.annual_max_usd == 180000.0
    assert usd_norm.currency == "USD"
    assert "$140k - $180k/yr USD" in usd_norm.formatted_usd_equiv

    # 2. EUR Range
    eur_norm = normalize_compensation("€80,000 - €100,000")
    assert eur_norm.currency == "EUR"
    assert eur_norm.annual_min_usd == round(80000.0 * 1.08, 2)
    assert eur_norm.annual_max_usd == round(100000.0 * 1.08, 2)

    # 3. GBP Single
    gbp_norm = normalize_compensation("£90k")
    assert gbp_norm.currency == "GBP"
    assert gbp_norm.annual_min_usd == round(90000.0 * 1.28, 2)

    # 4. Indian LPA (₹30 LPA)
    inr_norm = normalize_compensation("₹25 - ₹35 LPA")
    assert inr_norm.currency == "INR"
    assert inr_norm.annual_min_usd == round(2500000.0 * 0.012, 2)  # $30,000 USD
    assert inr_norm.annual_max_usd == round(3500000.0 * 0.012, 2)  # $42,000 USD

    # 5. Hourly Rate ($75/hr -> 2080h = $156,000/yr)
    hourly_norm = normalize_compensation("$75/hr")
    assert hourly_norm.is_hourly is True
    assert hourly_norm.annual_min_usd == 75.0 * 2080

    # 6. Equity Only
    equity_norm = normalize_compensation("Equity Only (1.5% grant)")
    assert equity_norm.is_equity_only is True
    assert equity_norm.annual_min_usd == 0.0


def test_anti_ghost_job_heuristics():
    # 1. Fresh Direct Job
    fresh_job = JobListing(
        id="fresh-1",
        title="Senior Python Backend Engineer",
        company="Stripe",
        location="San Francisco, CA",
        description="We are seeking a senior engineer with Python, FastAPI, and Postgres experience to scale payments.",
        tags=["Python", "FastAPI", "PostgreSQL"],
        url="https://boards.greenhouse.io/stripe/jobs/123",
        posted_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    v1 = detect_ghost_job(fresh_job)
    assert v1.risk_level == GhostRiskLevel.LOW_RISK
    assert not v1.is_ghost_job
    assert v1.risk_score < 30

    # 2. Stale Job > 60 Days
    stale_job = JobListing(
        id="stale-1",
        title="Backend Engineer",
        company="OldCo",
        location="Remote",
        description="Standard backend developer role.",
        url="https://example.com/jobs/99",
        posted_at=datetime.now(timezone.utc) - timedelta(days=75),
    )
    v2 = detect_ghost_job(stale_job)
    assert v2.risk_score >= 55
    assert any("Stale Listing" in f for f in v2.warning_flags)

    # 3. Staffing Agency Boilerplate Job
    agency_job = JobListing(
        id="agency-1",
        title="Lead Cloud Architect",
        company="Apex Staffing Solutions",
        location="Remote",
        description="Our direct client is a fast-growing client in fintech looking for confidential search talent.",
        url="https://example.com/agency/44",
        posted_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    v3 = detect_ghost_job(agency_job)
    assert v3.risk_score >= 45
    assert any("Staffing Agency" in f for f in v3.warning_flags)


@pytest.mark.asyncio
async def test_dead_link_verifier_probe():
    # 1. Simulated / Test Valid URL
    res1 = await verify_job_url("https://jobs.lever.co/mock-company/test-job-123")
    assert res1.is_accessible is True
    assert res1.ats_provider == "Lever"
    assert res1.status == LinkStatus.SIMULATED_VALID

    # 2. Empty URL
    res2 = await verify_job_url("")
    assert res2.is_accessible is False
    assert res2.status == LinkStatus.DEAD


def test_work_authorization_and_timezone():
    profile = UserProfile(
        location="San Francisco, CA",
        country_preference=["United States", "United Kingdom", "Germany", "India"],
    )

    # 1. US Only Job -> Candidate is in SF -> Compatible
    job_us = JobListing(
        title="Staff Engineer",
        company="US Tech",
        location="Remote (US Only)",
        description="Remote (US Only) role for backend development.",
        url="https://example.com",
    )
    verdict_us = evaluate_work_auth_and_timezone(job_us, profile)
    assert verdict_us.compatible is True
    assert verdict_us.has_geographic_restriction is True
    assert verdict_us.restriction_type == "US_ONLY"

    # 2. Security Clearance Job -> Incompatible
    job_clearance = JobListing(
        title="Defense Engineer",
        company="Defense Corp",
        location="Reston, VA",
        description="Requires active Secret clearance and US citizenship.",
        url="https://example.com",
    )
    verdict_cl = evaluate_work_auth_and_timezone(job_clearance, profile)
    assert verdict_cl.compatible is False
    assert verdict_cl.restriction_type == "CLEARANCE_REQUIRED"

    # 3. Timezone Overlap Test
    # SF (UTC-8) and London (UTC+0) = 8 hours diff -> 0 hours full overlap
    overlap = compute_business_hours_overlap(-8.0, 0.0)
    assert overlap == 0.0

    # SF (UTC-8) and Austin (UTC-6) = 2 hours diff -> 6.0 hours overlap
    overlap_us = compute_business_hours_overlap(-8.0, -6.0)
    assert overlap_us == 6.0


def test_high_leverage_cold_angle_generator():
    profile = UserProfile()
    jobs = get_mock_jobs()
    job = jobs[0]

    angle = generate_high_leverage_cold_angle(job, profile)
    assert angle.company == job.company
    assert angle.target_role == job.title
    assert "10M+" in angle.email_body_4_sentences
    assert "99.99%" in angle.email_body_4_sentences
    assert "mailto:" in angle.mailto_url
    assert len(angle.key_talking_points) >= 3
    assert len(angle.linkedin_inmail_body) < 350


def test_fit_evaluator_high_match():
    profile = UserProfile()
    jobs = get_mock_jobs()
    ai_job = next(j for j in jobs if j.id == "mock-job-01")
    
    eval_res = evaluate_job_fit(ai_job, profile)
    assert eval_res.score >= 80
    assert eval_res.match_tier in ("EXCELLENT", "STRONG")
    assert not eval_res.has_dealbreaker
    assert len(eval_res.matching_skills) >= 2
    assert eval_res.salary_normalized is not None
    assert eval_res.ghost_verdict is not None
    assert eval_res.work_auth_verdict is not None


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

    audit = audit_tailored_package(package, job, profile)
    assert audit.passed is True
    assert audit.ats_score >= 85
    assert len(audit.hallucination_flags) == 0


def test_pdf_compiler_instant_generation(tmp_path):
    profile = UserProfile()
    jobs = get_mock_jobs()
    job = jobs[0]
    package = draft_tailored_package(job, profile)

    pdf_filename = compile_ats_resume_pdf(package, profile)
    pdf_path = OUTPUT_DIR / pdf_filename
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000


def test_mock_interview_simulator():
    profile = UserProfile()
    jobs = get_mock_jobs()
    job = jobs[0]

    questions = generate_mock_interview_questions(job, profile)
    assert len(questions) == 4
    assert any(q.category == "Technical Architecture" for q in questions)
    assert any(q.category == "Behavioral & STAR" for q in questions)

    sample_answer = "I designed an asynchronous FastAPI ingestion pipeline using Redis queues and PostgreSQL, scaling to 10M daily requests."
    eval_res = evaluate_interview_answer(questions[0], sample_answer, profile)
    assert eval_res.score >= 70
    assert len(eval_res.strengths) >= 1
    assert len(eval_res.suggested_ideal_answer) > 20


def test_executive_morning_briefing_engine():
    profile = UserProfile()
    jobs = get_mock_jobs()
    pkgs_store = {}

    briefing = generate_executive_briefing(jobs, profile, pkgs_store)
    assert len(briefing.top_opportunities) <= 3
    assert len(briefing.precompiled_packages) == len(briefing.top_opportunities)
    assert briefing.total_scoured == len(jobs)
    assert briefing.qualified_count >= 1
    assert "Good morning" in briefing.greeting
    assert "Executive Morning Briefing" in briefing.executive_summary


def test_value_add_followup_agent():
    profile = UserProfile()
    jobs = get_mock_jobs()
    job = jobs[0]

    draft = generate_value_add_followup(job, profile, days_since_applied=6)
    assert draft.job_id == job.id
    assert draft.company == job.company
    assert "Re:" in draft.subject
    assert "6 days ago" in draft.body
    assert "Value-Add Technical Insight" in draft.follow_up_strategy
    assert len(draft.talking_point) > 20


def test_sqlite_persistence_and_repository():
    init_db()
    jobs = get_mock_jobs()
    job = jobs[0]
    profile = UserProfile(name="Test Candidate")
    eval_res = evaluate_job_fit(job, profile)

    save_job(job, eval_res)
    loaded = get_all_jobs_with_evaluations()
    assert len(loaded) >= 1

    app_rec = ApplicationRecord(
        job_id=job.id,
        company=job.company,
        title=job.title,
        status=TriageStatus.AWAITING_REPLY,
    )
    save_application(app_rec)
    apps = get_all_applications()
    assert job.id in apps
    assert apps[job.id].company == job.company

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
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "job" in data[0]
    assert "evaluation" in data[0]


def test_api_ghost_analysis_and_link_verifier():
    jobs = get_mock_jobs()
    job_id = jobs[0].id

    # Ghost Analysis Endpoint
    g_res = client.get(f"/api/jobs/{job_id}/ghost-analysis")
    assert g_res.status_code == 200
    g_data = g_res.json()
    assert g_data["status"] == "success"
    assert "ghost_verdict" in g_data
    assert "risk_score" in g_data["ghost_verdict"]

    # Link Verifier Endpoint
    l_res = client.post(f"/api/jobs/{job_id}/verify-link")
    assert l_res.status_code == 200
    l_data = l_res.json()
    assert l_data["status"] == "success"
    assert "link_verdict" in l_data
    assert l_data["link_verdict"]["is_accessible"] is True


def test_api_cold_angle_endpoint():
    jobs = get_mock_jobs()
    job_id = jobs[0].id

    res = client.post(f"/api/jobs/{job_id}/cold-angle")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "cold_angle" in data
    assert "10M+" in data["cold_angle"]["email_body_4_sentences"]
    assert "mailto:" in data["cold_angle"]["mailto_url"]


def test_api_tools_normalize_salary_and_work_auth():
    # 1. Salary Tool
    s_res = client.post("/api/tools/normalize-salary", json={"raw_salary": "€85,000 - €105,000"})
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert s_data["status"] == "success"
    assert s_data["normalized_salary"]["currency"] == "EUR"
    assert s_data["normalized_salary"]["annual_min_usd"] > 80000

    # 2. Work Auth Tool
    w_res = client.post("/api/tools/check-work-auth", json={
        "location": "Remote (US Only)",
        "country": "United States",
        "description": "Standard engineering position in USA."
    })
    assert w_res.status_code == 200
    w_data = w_res.json()
    assert w_data["status"] == "success"
    assert "work_auth_verdict" in w_data
    assert w_data["work_auth_verdict"]["compatible"] is True


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
    apply_res = client.post(f"/api/pipeline/{job_id}/apply")
    assert apply_res.status_code == 200
    app_rec = apply_res.json()["application"]
    assert app_rec["status"] == "awaiting_reply"
    assert app_rec["days_since_applied"] == 0

    # 2. Get Radar
    radar_res = client.get("/api/pipeline/radar")
    assert radar_res.status_code == 200
    radar = radar_res.json()
    assert radar["total_active"] >= 1
    assert "follow_up_due_count" in radar

    # 3. Generate Follow-Up
    follow_res = client.post(f"/api/pipeline/{job_id}/follow-up/draft")
    assert follow_res.status_code == 200
    draft = follow_res.json()
    assert draft["company"] == jobs[0].company
    assert "Re:" in draft["subject"]

    # 4. Record Follow-Up Sent
    send_res = client.post(f"/api/pipeline/{job_id}/follow-up/send")
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
