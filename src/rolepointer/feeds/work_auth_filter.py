"""
RolePointer — Work Authorization & Timezone Compatibility Evaluator
Performs:
1. Visa & Geographic Restriction Hard-Filtering: Detects "Remote (US Only)",
   "No sponsorship available", "Security Clearance Required", "EU Work Rights".
2. Timezone Overlap Calculation: Evaluates UTC overlap during standard business hours
   (requires >=4 hours daily overlap for remote collaboration).
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from rolepointer.models.schemas import (
    JobListing, UserProfile, WorkplaceType, WorkAuthVerdict
)


# ── Timezone Map (Approximate UTC Offsets in Hours) ───────────────────────────

LOCATION_UTC_OFFSETS = {
    # US & Canada
    "san francisco": -8.0,
    "california": -8.0,
    "seattle": -8.0,
    "los angeles": -8.0,
    "us pacific": -8.0,
    "us mountain": -7.0,
    "denver": -7.0,
    "us central": -6.0,
    "austin": -6.0,
    "chicago": -6.0,
    "us eastern": -5.0,
    "new york": -5.0,
    "boston": -5.0,
    "toronto": -5.0,
    "united states": -6.0,
    "usa": -6.0,
    "us": -6.0,
    "canada": -5.0,

    # UK & Europe
    "london": 0.0,
    "united kingdom": 0.0,
    "uk": 0.0,
    "ireland": 0.0,
    "dublin": 0.0,
    "berlin": 1.0,
    "germany": 1.0,
    "amsterdam": 1.0,
    "netherlands": 1.0,
    "paris": 1.0,
    "france": 1.0,
    "switzerland": 1.0,
    "zurich": 1.0,
    "europe": 1.0,
    "eu": 1.0,
    "emea": 1.0,

    # Asia & Oceania
    "india": 5.5,
    "bangalore": 5.5,
    "bengaluru": 5.5,
    "delhi": 5.5,
    "mumbai": 5.5,
    "hyderabad": 5.5,
    "singapore": 8.0,
    "sydney": 10.0,
    "australia": 10.0,
    "tokyo": 9.0,
    "japan": 9.0,
}


def _infer_utc_offset(loc_str: str) -> float:
    """Infers approximate UTC offset from string."""
    loc_lower = loc_str.lower()
    for key, offset in LOCATION_UTC_OFFSETS.items():
        if key in loc_lower:
            return offset
    return 0.0  # Default UTC


def compute_business_hours_overlap(offset_a: float, offset_b: float) -> float:
    """
    Computes overlap between two standard 9:00 - 17:00 (8-hour) work schedules.
    Returns overlapping hours (0.0 to 8.0).
    """
    diff = abs(offset_a - offset_b)
    overlap = max(0.0, 8.0 - diff)
    return round(overlap, 1)


# ── Geographic & Visa Restriction Regexes ─────────────────────────────────────

US_ONLY_PATTERNS = [
    r"\bremote\s*\(?\s*(?:us|usa|united states)\s*only\)?\b",
    r"\bmust\s+be\s+located\s+in\s+the\s+(?:us|usa|united states)\b",
    r"\bus\s+citizenship\s+(?:or|and)\s+green\s+card\s+required\b",
    r"\bus\s+based\s+candidates\s+only\b",
    r"\bmust\s+reside\s+in\s+the\s+united\s+states\b",
]

CLEARANCE_PATTERNS = [
    r"\bactive\s+secret\s+clearance\b",
    r"\btop\s+secret\s+clearance\b",
    r"\bsecurity\s+clearance\s+required\b",
    r"\bts/sci\b",
    r"\bpolygraph\s+required\b",
]

EU_ONLY_PATTERNS = [
    r"\bremote\s*\(?\s*(?:eu|europe|emea)\s*only\)?\b",
    r"\bmust\s+have\s+eu\s+citizenship\b",
    r"\beu\s+work\s+permit\s+required\b",
    r"\bmust\s+be\s+located\s+in\s+(?:germany|uk|europe)\b",
]

NO_SPONSORSHIP_PATTERNS = [
    r"\bno\s+visa\s+sponsorship\b",
    r"\bunable\s+to\s+sponsor\b",
    r"\bwithout\s+sponsorship\b",
    r"\bwill\s+not\s+sponsor\b",
]


def evaluate_work_auth_and_timezone(job: JobListing, profile: UserProfile) -> WorkAuthVerdict:
    """
    Evaluates geographic restrictions, visa sponsorship, and timezone alignment.
    """
    job_text = f"{job.title} {job.location} {job.country or ''} {job.city or ''} {job.description}".lower()
    candidate_loc = profile.location.lower()
    candidate_countries = [c.lower() for c in profile.country_preference]

    reasons: List[str] = []
    has_geo_restriction = False
    restriction_type: Optional[str] = None
    is_compatible = True

    # 1. Security Clearance Check
    for pat in CLEARANCE_PATTERNS:
        if re.search(pat, job_text):
            has_geo_restriction = True
            restriction_type = "CLEARANCE_REQUIRED"
            reasons.append("Requires active US Department of Defense / Government Security Clearance.")
            is_compatible = False
            break

    # 2. US-Only Constraint Check
    if not has_geo_restriction:
        for pat in US_ONLY_PATTERNS:
            if re.search(pat, job_text):
                has_geo_restriction = True
                restriction_type = "US_ONLY"
                reasons.append("Strict 'US Candidates Only' restriction detected.")
                # Check if candidate is based in US or prefers US
                if not any(us_key in candidate_loc or us_key in " ".join(candidate_countries) for us_key in ["united states", "usa", "us", "san francisco", "new york", "austin", "ca"]):
                    is_compatible = False
                break

    # 3. EU-Only Constraint Check
    if not has_geo_restriction:
        for pat in EU_ONLY_PATTERNS:
            if re.search(pat, job_text):
                has_geo_restriction = True
                restriction_type = "EU_ONLY"
                reasons.append("Strict 'EU / EMEA Only' work authorization required.")
                if not any(eu_key in candidate_loc or eu_key in " ".join(candidate_countries) for eu_key in ["germany", "uk", "united kingdom", "london", "berlin", "europe", "eu", "france"]):
                    is_compatible = False
                break

    # 4. No Sponsorship Check
    if any(re.search(pat, job_text) for pat in NO_SPONSORSHIP_PATTERNS):
        reasons.append("Employer explicitly cannot provide visa sponsorship.")

    # 5. Timezone Overlap Calculation
    candidate_offset = _infer_utc_offset(profile.location)
    job_loc_str = f"{job.location} {job.country or ''} {job.city or ''}"
    job_offset = _infer_utc_offset(job_loc_str)

    if job.workplace_type == WorkplaceType.REMOTE and job_offset == 0.0 and job.country:
        job_offset = _infer_utc_offset(job.country)

    overlap_hours = compute_business_hours_overlap(candidate_offset, job_offset)
    tz_compatible = overlap_hours >= 4.0

    if not tz_compatible and job.workplace_type == WorkplaceType.REMOTE:
        reasons.append(f"Low daily working hours overlap ({overlap_hours}h vs. recommended >=4h).")
        if overlap_hours < 2.0:
            is_compatible = False

    # 6. Synthesize Explanation
    if not is_compatible:
        explanation = f"⚠️ Work authorization or timezone mismatch: {'; '.join(reasons)}"
    elif has_geo_restriction:
        explanation = f"✓ Geographic criteria verified for candidate ({restriction_type}). {overlap_hours}h UTC overlap."
    else:
        explanation = f"✓ Fully compatible. {overlap_hours} hours of daily collaboration overlap."

    return WorkAuthVerdict(
        job_id=job.id,
        compatible=is_compatible,
        has_geographic_restriction=has_geo_restriction,
        restriction_type=restriction_type,
        timezone_overlap_hours=overlap_hours,
        timezone_compatible=tz_compatible,
        explanation=explanation,
        reasons=reasons,
    )
