"""
RolePointer — Pydantic Schemas & Data Contracts
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, computed_field


class WorkplaceType(str, Enum):
    REMOTE = "REMOTE"
    ONSITE = "ONSITE"
    HYBRID = "HYBRID"
    ANY = "ANY"


class ExperienceLevel(str, Enum):
    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"
    STAFF_LEAD = "STAFF_LEAD"
    ANY = "ANY"


class TriageStatus(str, Enum):
    DISCOVERED = "discovered"
    SAVED = "saved"
    SKIPPED = "skipped"
    PACKAGE_PREPARED = "package_prepared"
    APPLIED = "applied"
    AWAITING_REPLY = "awaiting_reply"
    FOLLOW_UP_DUE = "follow_up_due"
    INTERVIEWING = "interviewing"
    REJECTED = "rejected"
    OFFER = "offer"


# ── Ghost Job Classifications ──────────────────────────────────────────────────

class GhostRiskLevel(str, Enum):
    LOW_RISK = "LOW_RISK"            # Verified active & genuine posting
    MODERATE_RISK = "MODERATE_RISK"  # Aged >45 days or agency markers
    HIGH_GHOST_RISK = "HIGH_GHOST_RISK"  # Strong ghost job signals (>60d, agency boilerplate)


class GhostJobVerdict(BaseModel):
    job_id: str
    risk_score: int = Field(ge=0, le=100, default=10)
    risk_level: GhostRiskLevel = GhostRiskLevel.LOW_RISK
    is_ghost_job: bool = False
    warning_flags: List[str] = Field(default_factory=list)
    signals: List[str] = Field(default_factory=list)
    explanation: str = "Posting appears fresh, specific, and directly posted by hiring employer."


# ── Dead Link Classifications ──────────────────────────────────────────────────

class LinkStatus(str, Enum):
    ACTIVE = "ACTIVE"              # 200 OK, application form detected
    DEAD = "DEAD"                  # 404/410, page removed
    CLOSED = "CLOSED"              # 200 OK but text shows 'position closed/filled'
    AUTH_REQUIRED = "AUTH_REQUIRED" # 401/403 login barrier
    UNVERIFIED_TIMEOUT = "UNVERIFIED_TIMEOUT" # Probe timed out
    SIMULATED_VALID = "SIMULATED_VALID" # Mock / test URL verified


class LinkStatusVerdict(BaseModel):
    url: str
    status: LinkStatus = LinkStatus.ACTIVE
    http_status_code: Optional[int] = 200
    is_accessible: bool = True
    ats_provider: str = "Direct"
    status_message: str = "Application portal is live and accepting submissions."
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Compensation & Currency Normalization ─────────────────────────────────────

class NormalizedSalary(BaseModel):
    raw_text: str = ""
    currency: str = "USD"
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    is_hourly: bool = False
    is_annual: bool = True
    is_equity_only: bool = False
    is_ote: bool = False
    base_min_usd: Optional[float] = None
    base_max_usd: Optional[float] = None
    annual_min_usd: Optional[float] = None
    annual_max_usd: Optional[float] = None
    formatted_usd_equiv: str = "Not Disclosed"
    confidence: str = "HIGH"


# ── Work Authorization & Timezone Compatibility ───────────────────────────────

class WorkAuthVerdict(BaseModel):
    job_id: str
    compatible: bool = True
    has_geographic_restriction: bool = False
    restriction_type: Optional[str] = None  # "US_ONLY", "EU_ONLY", "CLEARANCE_REQUIRED", "NO_SPONSORSHIP"
    timezone_overlap_hours: float = 8.0
    timezone_compatible: bool = True
    explanation: str = "Candidate cleared for work authorization and meets timezone collaboration requirements."
    reasons: List[str] = Field(default_factory=list)


# ── High-Leverage Cold Outreach Angle ─────────────────────────────────────────

class ColdAngleResult(BaseModel):
    job_id: str
    company: str
    target_role: str
    detected_tech_challenge: str
    email_subject: str
    email_body_4_sentences: str
    linkedin_inmail_body: str
    key_talking_points: List[str] = Field(default_factory=list)
    mailto_url: str = ""
    rationale: str = ""


# ── Application Tracking & Response Radar ──────────────────────────────────

class ApplicationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    company: str
    title: str
    applied_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    days_since_applied: int = 0
    status: TriageStatus = TriageStatus.AWAITING_REPLY
    follow_up_due: bool = False
    follow_up_count: int = 0
    last_follow_up_at: Optional[datetime] = None
    direct_pitch_letter: Optional[str] = None


class FollowUpDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    company: str
    role: str
    days_since_outreach: int
    follow_up_strategy: str = "Value-Add Technical Insight"
    subject: str
    body: str
    talking_point: str
    recommended_action: str = "Send 1-Click Value-Add Follow-Up"


# ── Executive Morning Briefing ───────────────────────────────────────────────

class ExecutiveBriefing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    date: str
    greeting: str
    total_scoured: int
    qualified_count: int
    top_opportunities: List[JobListing] = Field(default_factory=list)
    top_evaluations: List[FitEvaluation] = Field(default_factory=list)
    precompiled_packages: List[TailoredPackage] = Field(default_factory=list)
    executive_summary: str


# ── User Profile ─────────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    id: str = Field(default="default_user")
    name: str = "Alex Morgan"
    email: str = "alex.morgan@example.com"
    phone: str = "+1 (555) 234-5678"
    location: str = "San Francisco, CA"
    country_preference: List[str] = Field(default_factory=lambda: ["United States", "United Kingdom", "Germany", "India"])
    city_preference: List[str] = Field(default_factory=lambda: ["San Francisco", "London", "Bangalore", "Berlin", "New York"])
    preferred_workplace_types: List[WorkplaceType] = Field(default_factory=lambda: [WorkplaceType.REMOTE, WorkplaceType.HYBRID, WorkplaceType.ONSITE])
    target_domains: List[str] = Field(default_factory=lambda: ["AI/ML", "Backend", "Fullstack", "DevOps/Cloud"])
    target_roles: List[str] = Field(default_factory=lambda: [
        "Senior Backend Engineer", "AI Systems Engineer", "Full Stack Developer", "Platform Engineer"
    ])
    skills: List[str] = Field(default_factory=lambda: [
        "Python", "FastAPI", "PostgreSQL", "AWS", "Docker", "Kubernetes", "PyTorch", "LangChain", "TypeScript", "React", "Redis"
    ])
    experience_summary: str = (
        "Senior Software Engineer with 6+ years building distributed backend architectures, "
        "LLM agent pipelines, and high-throughput microservices in Python, FastAPI, and AWS. "
        "Led migration to Kubernetes microservices serving 10M+ daily requests with 99.99% SLA."
    )
    min_salary_floor: Optional[float] = 120000.0
    dealbreakers: List[str] = Field(default_factory=lambda: [
        "unpaid overtime", "on-call weekend shifts", "crypto/gambling", "staffing agency", "legacy php"
    ])


# ── Job Listing ──────────────────────────────────────────────────────────────

class JobListing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    company: str
    location: str
    country: Optional[str] = None
    city: Optional[str] = None
    workplace_type: WorkplaceType = WorkplaceType.REMOTE
    domain: str = "Backend"
    experience_level: ExperienceLevel = ExperienceLevel.SENIOR
    salary_range: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    tags: List[str] = Field(default_factory=list)
    description: str
    url: str
    source: str = "Direct"
    posted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    triage_status: TriageStatus = TriageStatus.DISCOVERED


# ── Dealbreaker & Fit Evaluation ──────────────────────────────────────────────

class DealbreakerAlert(BaseModel):
    rule: str
    triggered: bool
    explanation: str


class FitEvaluation(BaseModel):
    job_id: str
    score: int = Field(ge=0, le=100)  # 0 to 100
    match_tier: str = "STRONG"        # EXCELLENT, STRONG, MODERATE, POOR
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    dealbreaker_alerts: List[DealbreakerAlert] = Field(default_factory=list)
    has_dealbreaker: bool = False
    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    summary: str = ""
    ghost_verdict: Optional[GhostJobVerdict] = None
    salary_normalized: Optional[NormalizedSalary] = None
    work_auth_verdict: Optional[WorkAuthVerdict] = None


# ── Tailored Package & Reviewer ───────────────────────────────────────────────

class ReviewAuditResult(BaseModel):
    passed: bool = True
    ats_score: int = Field(ge=0, le=100, default=92)
    keyword_match_pct: float = 88.5
    hallucination_flags: List[str] = Field(default_factory=list)
    action_verb_count: int = 6
    recommendations: List[str] = Field(default_factory=list)


class TailoredPackage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    company: str
    title: str
    tailored_summary: str
    tailored_experience_bullets: List[str] = Field(default_factory=list)
    targeted_skills: List[str] = Field(default_factory=list)
    direct_pitch_letter: str  # 4-sentence direct pitch
    audit_result: ReviewAuditResult = Field(default_factory=ReviewAuditResult)
    pdf_filename: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Mock Interview Simulator ──────────────────────────────────────────────────

class MockInterviewQuestion(BaseModel):
    question_id: int
    category: str  # Technical, System Design, Behavioral, Culture
    question: str
    guidance: str


class MockInterviewEvaluation(BaseModel):
    question_id: int
    user_answer: str
    score: int = Field(ge=0, le=100)
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    suggested_ideal_answer: str


class MockInterviewSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    company: str
    role: str
    questions: List[MockInterviewQuestion] = Field(default_factory=list)
    evaluations: List[MockInterviewEvaluation] = Field(default_factory=list)
    overall_score: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Feed Search Filter Request ────────────────────────────────────────────────

class FeedFilterQuery(BaseModel):
    domain: Optional[str] = None
    workplace_type: Optional[WorkplaceType] = None
    country: Optional[str] = None
    city: Optional[str] = None
    min_score: Optional[int] = None
    exclude_dealbreakers: bool = True
