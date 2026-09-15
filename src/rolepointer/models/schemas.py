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
