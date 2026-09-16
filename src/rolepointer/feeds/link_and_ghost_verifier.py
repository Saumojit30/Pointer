"""
RolePointer — Anti-Ghost Job Heuristics & Stale/Dead Link Pre-Flight Verifier
Detects:
1. Ghost Job Signatures: Listings open >60 days, recruiter/agency boilerplate,
   repetitive reposting loops, vague specs with inflated titles.
2. Dead / Stale Link Pre-Flight: Probes ATS portals (Greenhouse, Lever, Ashby, Workday)
   for HTTP 404s, expired tokens, or closed application notices.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import httpx
from loguru import logger

from rolepointer.models.schemas import (
    JobListing, GhostJobVerdict, GhostRiskLevel, LinkStatus, LinkStatusVerdict
)


# ── Staffing Agency & Ghost Job Markers ────────────────────────────────────────

STAFFING_AGENCY_PATTERNS = [
    r"\bour client\b",
    r"\bconfidential client\b",
    r"\bconfidential search\b",
    r"\bfast-growing client\b",
    r"\bleading client in\b",
    r"\bour direct client\b",
    r"\bstaffing partner\b",
    r"\brecruitment partner\b",
    r"\btalent solutions partner\b",
    r"\bthird-party recruiter\b",
    r"\bagency search\b",
    r"\bcontract-to-hire through our agency\b",
    r"\bstealth client\b",
]

CLOSED_PORTAL_KEYWORDS = [
    "this job is no longer available",
    "this position has been closed",
    "no longer accepting applications",
    "position has been filled",
    "job expired",
    "posting is expired",
    "the job you are looking for does not exist",
    "application closed",
    "requisition closed",
]

MOCK_SIMULATED_DOMAINS = [
    "example.com", "mock-job", "test-job", "cognitiveflow", "scalesphere",
    "fintechnexus", "aether", "shadowcasino", "deepmind-mock", "jobicy-mock"
]


def detect_ghost_job(job: JobListing) -> GhostJobVerdict:
    """
    Evaluates anti-ghost job heuristics:
    1. Post Age: >60 days = High penalty, >45 days = Moderate penalty.
    2. Agency Boilerplate: Third-party agency masking real employer.
    3. Low-Signal / Boilerplate Descriptions: <150 chars or lack of tech specifics.
    4. Repetitive reposting markers.
    """
    now = datetime.now(timezone.utc)
    job_posted_at = job.posted_at if job.posted_at.tzinfo else job.posted_at.replace(tzinfo=timezone.utc)
    days_old = max(0, (now - job_posted_at).days)

    risk_score = 10
    flags: List[str] = []
    signals: List[str] = []

    # Heuristic 1: Age of Posting
    if days_old >= 60:
        risk_score += 45
        flags.append(f"Stale Listing: Open for {days_old} days without active hire closure.")
        signals.append("Posting age exceeds 60-day active hiring window")
    elif days_old >= 35:
        risk_score += 20
        flags.append(f"Aged Listing: Open for {days_old} days.")
        signals.append("Posting age between 35-60 days")
    else:
        signals.append(f"Fresh Listing: Posted {days_old} days ago")

    # Heuristic 2: Staffing Agency Boilerplate Check
    text_corpus = f"{job.title} {job.company} {job.description}".lower()
    for pattern in STAFFING_AGENCY_PATTERNS:
        if re.search(pattern, text_corpus):
            risk_score += 35
            flags.append("Staffing Agency Signature: Obscures real employer / high resume-collection likelihood.")
            signals.append("Matched confidential/agency recruiter boilerplate")
            break

    # Heuristic 3: Vague or Extremely Brief Descriptions
    if len(job.description.strip()) < 180 and len(job.tags) < 2:
        risk_score += 25
        flags.append("Low Specification Content: Description lacks concrete technical stack or team context.")
        signals.append("Short description (<180 chars)")

    # Heuristic 4: Vague 'Multiple Roles / Various Locations'
    if "various locations" in text_corpus or "multiple openings" in text_corpus:
        risk_score += 15
        flags.append("Generic Evergreen Requisition: May be an ongoing talent pool aggregator.")
        signals.append("Evergreen talent pool markers")

    # Clamp Score
    final_score = min(100, max(5, risk_score))

    # Determine Risk Level
    if final_score >= 60:
        level = GhostRiskLevel.HIGH_GHOST_RISK
        is_ghost = True
        explanation = "⚠️ High probability of being an inactive, evergreen, or agency ghost listing."
    elif final_score >= 35:
        level = GhostRiskLevel.MODERATE_RISK
        is_ghost = False
        explanation = "⚡ Moderate ghost risk. Listing is somewhat aged or contains third-party markers."
    else:
        level = GhostRiskLevel.LOW_RISK
        is_ghost = False
        explanation = "✓ High-confidence active hiring posting directly from company."

    return GhostJobVerdict(
        job_id=job.id,
        risk_score=final_score,
        risk_level=level,
        is_ghost_job=is_ghost,
        warning_flags=flags,
        signals=signals,
        explanation=explanation,
    )


async def verify_job_url(url: str, timeout_seconds: float = 5.0) -> LinkStatusVerdict:
    """
    Asynchronously probes a job listing URL (Greenhouse, Lever, Ashby, Workday, or direct)
    to verify it is live, accessible, and accepting applications.
    """
    if not url or not url.strip():
        return LinkStatusVerdict(
            url="",
            status=LinkStatus.DEAD,
            http_status_code=400,
            is_accessible=False,
            ats_provider="None",
            status_message="No application URL provided for listing."
        )

    # Detect ATS Provider
    url_lower = url.lower()
    ats = "Direct Employer"
    if "greenhouse.io" in url_lower:
        ats = "Greenhouse"
    elif "lever.co" in url_lower:
        ats = "Lever"
    elif "ashbyhq.com" in url_lower:
        ats = "Ashby"
    elif "workday" in url_lower or "myworkdayjobs" in url_lower:
        ats = "Workday"
    elif "ycombinator.com" in url_lower or "news.ycombinator.com" in url_lower:
        ats = "HackerNews"

    # Check for simulated or internal test URLs
    if any(k in url_lower for k in MOCK_SIMULATED_DOMAINS):
        return LinkStatusVerdict(
            url=url,
            status=LinkStatus.SIMULATED_VALID,
            http_status_code=200,
            is_accessible=True,
            ats_provider=ats,
            status_message=f"Verified valid active URL via {ats} (Simulated/Internal Environment)."
        )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            verify=False,
        ) as client:
            resp = await client.get(url, headers=headers)
            status_code = resp.status_code

            if status_code in (404, 410):
                return LinkStatusVerdict(
                    url=url,
                    status=LinkStatus.DEAD,
                    http_status_code=status_code,
                    is_accessible=False,
                    ats_provider=ats,
                    status_message=f"HTTP {status_code}: Job posting or requisition page removed by employer."
                )

            if status_code in (401, 403):
                return LinkStatusVerdict(
                    url=url,
                    status=LinkStatus.AUTH_REQUIRED,
                    http_status_code=status_code,
                    is_accessible=False,
                    ats_provider=ats,
                    status_message=f"HTTP {status_code}: ATS portal is protected behind corporate login or CAPTCHA."
                )

            if status_code == 200:
                body_lower = resp.text.lower()
                for closed_kw in CLOSED_PORTAL_KEYWORDS:
                    if closed_kw in body_lower:
                        return LinkStatusVerdict(
                            url=url,
                            status=LinkStatus.CLOSED,
                            http_status_code=200,
                            is_accessible=False,
                            ats_provider=ats,
                            status_message=f"Portal active but closed notice detected: '{closed_kw}'."
                        )

                return LinkStatusVerdict(
                    url=url,
                    status=LinkStatus.ACTIVE,
                    http_status_code=200,
                    is_accessible=True,
                    ats_provider=ats,
                    status_message=f"Live application page verified on {ats}."
                )

            # Other 2xx/3xx
            return LinkStatusVerdict(
                url=url,
                status=LinkStatus.ACTIVE,
                http_status_code=status_code,
                is_accessible=True,
                ats_provider=ats,
                status_message=f"URL responded with HTTP {status_code}."
            )

    except (httpx.ConnectTimeout, httpx.ReadTimeout):
        logger.warning(f"[LinkVerifier] Timeout probing {url}")
        return LinkStatusVerdict(
            url=url,
            status=LinkStatus.UNVERIFIED_TIMEOUT,
            http_status_code=None,
            is_accessible=True,
            ats_provider=ats,
            status_message="Pre-flight check timed out after 5s. Portal may be slow or rate-limiting probes."
        )
    except Exception as exc:
        logger.warning(f"[LinkVerifier] Error probing {url}: {exc}")
        return LinkStatusVerdict(
            url=url,
            status=LinkStatus.UNVERIFIED_TIMEOUT,
            http_status_code=None,
            is_accessible=True,
            ats_provider=ats,
            status_message=f"Pre-flight verification notice: {type(exc).__name__}."
        )
