"""
RolePointer — Curated Golden Evaluation Benchmark Dataset
Standardized test cases with known ground truth across role types, salary boundaries,
geographic restrictions, and ghost listing heuristics.
"""
from datetime import datetime, timedelta, timezone
from rolepointer.models.schemas import (
    JobListing, UserProfile, WorkplaceType, ExperienceLevel,
    GhostRiskLevel
)
from rolepointer.evals.schemas import EvalCase

now = datetime.now(timezone.utc)

# Ground-truth Candidate Profiles
PROFILE_SENIOR_BACKEND = UserProfile(
    name="Alex Mercer",
    title="Staff / Senior Distributed Systems Engineer",
    email="alex.mercer@engineer.io",
    phone="+1 (415) 890-1234",
    location="San Francisco, CA",
    target_roles=["Senior Backend Engineer", "Staff Software Engineer", "Distributed Systems Engineer"],
    skills=["Python", "Go", "PostgreSQL", "Kafka", "AWS", "Docker", "Kubernetes", "Redis", "FastAPI"],
    salary_floor_usd=130000.0,
    anti_goals=["on-call weekend shifts", "crypto", "gambling", "staffing agency"],
    summary="10+ years architecting high-throughput distributed backends handling 50k+ RPS with 99.99% uptime."
)

PROFILE_FULLSTACK_DEV = UserProfile(
    name="Maya Lin",
    title="Lead Fullstack Engineer",
    email="maya.lin@dev.io",
    phone="+1 (212) 555-0199",
    location="New York, NY",
    target_roles=["Senior Fullstack Engineer", "Lead Frontend Engineer"],
    skills=["TypeScript", "React", "Next.js", "Node.js", "GraphQL", "Tailwind CSS", "PostgreSQL", "FastAPI"],
    salary_floor_usd=120000.0,
    anti_goals=["unpaid overtime", "crypto"],
    summary="8 years building modern web applications, scaling frontend state architectures and REST/GraphQL APIs."
)


BENCHMARK_CASES = [
    # Case 1: High-Fit Backend Match (Excellent Fit, Low Ghost Risk, 0 Dealbreakers)
    EvalCase(
        id="EVAL-001",
        name="High-Fit Distributed Systems Role",
        description="Senior Backend listing matching candidate stack perfectly with strong comp and verified portal.",
        job_listing=JobListing(
            id="job-eval-001",
            title="Senior Distributed Systems Engineer",
            company="CloudScale AI",
            location="San Francisco, CA",
            workplace_type=WorkplaceType.HYBRID,
            description="We are building real-time event streaming pipelines. Looking for experts in Go, Python, Kafka, and PostgreSQL. $165,000 - $195,000 base salary.",
            salary_min=165000.0,
            salary_max=195000.0,
            tags=["Go", "Python", "Kafka", "PostgreSQL", "Kubernetes"],
            experience_level=ExperienceLevel.SENIOR,
            url="https://jobs.ashbyhq.com/cloudscale/eval-001",
            posted_at=now - timedelta(days=5),
            source="Ashby"
        ),
        candidate_profile=PROFILE_SENIOR_BACKEND,
        expected_match_tier="EXCELLENT",
        expected_dealbreaker=False,
        expected_ghost_risk=GhostRiskLevel.LOW_RISK,
    ),

    # Case 2: Salary Dealbreaker Violation
    EvalCase(
        id="EVAL-002",
        name="Salary Floor Dealbreaker Role",
        description="Job pays $85,000 which is far below candidate's $130,000 salary floor.",
        job_listing=JobListing(
            id="job-eval-002",
            title="Staff Backend Engineer",
            company="BudgetTech Labs",
            location="Remote",
            workplace_type=WorkplaceType.REMOTE,
            description="Seeking Python and PostgreSQL engineer. Compensation is $80,000 to $85,000 maximum.",
            salary_min=80000.0,
            salary_max=85000.0,
            tags=["Python", "PostgreSQL"],
            experience_level=ExperienceLevel.SENIOR,
            url="https://boards.greenhouse.io/budgettech/eval-002",
            posted_at=now - timedelta(days=3),
            source="Greenhouse"
        ),
        candidate_profile=PROFILE_SENIOR_BACKEND,
        expected_match_tier="STRONG",
        expected_dealbreaker=True,
        expected_ghost_risk=GhostRiskLevel.LOW_RISK,
        expected_dealbreaker_reason_contains="Salary"
    ),

    # Case 3: Anti-Goal Dealbreaker (Weekend On-Call Shifts)
    EvalCase(
        id="EVAL-003",
        name="Anti-Goal On-Call Dealbreaker Role",
        description="Job requires mandatory 24/7 weekend on-call pager rotation explicitly violating candidate anti-goals.",
        job_listing=JobListing(
            id="job-eval-003",
            title="Senior Infrastructure & Reliability Engineer",
            company="OpsHeavy Systems",
            location="Remote",
            workplace_type=WorkplaceType.REMOTE,
            description="High pressure environment. Requires mandatory on-call weekend shifts and 24/7 pagerduty rotation. $150k-$180k.",
            salary_min=150000.0,
            salary_max=180000.0,
            tags=["Go", "Docker", "Kubernetes", "AWS"],
            experience_level=ExperienceLevel.SENIOR,
            url="https://jobs.lever.co/opsheavy/eval-003",
            posted_at=now - timedelta(days=8),
            source="Lever"
        ),
        candidate_profile=PROFILE_SENIOR_BACKEND,
        expected_match_tier="STRONG",
        expected_dealbreaker=True,
        expected_ghost_risk=GhostRiskLevel.LOW_RISK,
        expected_dealbreaker_reason_contains="on-call"
    ),

    # Case 4: Ghost Job Heuristic Repost (>70 Days Old + Staffing Agency Boilerplate)
    EvalCase(
        id="EVAL-004",
        name="Ghost Job Agency Repost",
        description="Listing posted 75 days ago with classic recruiter staffing agency boilerplate.",
        job_listing=JobListing(
            id="job-eval-004",
            title="Senior Software Engineer - Direct Client",
            company="Confidential Recruiting Partners",
            location="San Francisco, CA",
            workplace_type=WorkplaceType.HYBRID,
            description="Our direct client is confidential. Multiple openings available for immediate hire. Please submit resume.",
            tags=["Python", "SQL"],
            experience_level=ExperienceLevel.SENIOR,
            url="https://agency-portal.com/jobs/eval-004",
            posted_at=now - timedelta(days=75),
            source="External Recruiter"
        ),
        candidate_profile=PROFILE_SENIOR_BACKEND,
        expected_match_tier="MODERATE",
        expected_dealbreaker=True,
        expected_ghost_risk=GhostRiskLevel.HIGH_GHOST_RISK,
    ),

    # Case 5: Verified High-Fit Fullstack Engineer
    EvalCase(
        id="EVAL-005",
        name="High-Fit Fullstack Next.js/FastAPI Role",
        description="Modern product company seeking React, Next.js, and FastAPI experience.",
        job_listing=JobListing(
            id="job-eval-005",
            title="Lead Product Engineer (Fullstack)",
            company="Aether Interface",
            location="New York, NY",
            workplace_type=WorkplaceType.HYBRID,
            description="Scale our collaborative design platform. Stack: React, Next.js, TypeScript, FastAPI, and PostgreSQL. $155,000 - $185,000.",
            salary_min=155000.0,
            salary_max=185000.0,
            tags=["React", "Next.js", "TypeScript", "FastAPI", "GraphQL"],
            experience_level=ExperienceLevel.STAFF_LEAD,
            url="https://jobs.ashbyhq.com/aether/eval-005",
            posted_at=now - timedelta(days=4),
            source="Ashby"
        ),
        candidate_profile=PROFILE_FULLSTACK_DEV,
        expected_match_tier="EXCELLENT",
        expected_dealbreaker=False,
        expected_ghost_risk=GhostRiskLevel.LOW_RISK,
    ),
]
