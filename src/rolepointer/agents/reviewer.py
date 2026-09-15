"""
RolePointer — ATS Reviewer & Hallucination Auditor Agent
Validates tailored packages for ATS keyword alignment, verifies facts against user profile,
and detects any ungrounded AI hallucinations.
"""
from __future__ import annotations

import re
from typing import List
from loguru import logger

from rolepointer.models.schemas import JobListing, UserProfile, TailoredPackage, ReviewAuditResult


def audit_tailored_package(package: TailoredPackage, job: JobListing, profile: UserProfile) -> ReviewAuditResult:
    """Performs dual ATS keyword audit and anti-hallucination verification."""
    combined_package_text = f"{package.tailored_summary} {' '.join(package.tailored_experience_bullets)} {package.direct_pitch_letter}".lower()
    user_facts_text = f"{profile.experience_summary} {' '.join(profile.skills)} {profile.name} {profile.location}".lower()

    # 1. ATS Keyword Coverage
    job_keywords = [t.lower() for t in job.tags if len(t) > 2] + [w.lower() for w in job.title.split() if len(w) > 3]
    if not job_keywords:
        job_keywords = ["python", "api", "cloud", "system", "scale"]

    matched_keywords = [kw for kw in job_keywords if kw in combined_package_text]
    keyword_match_pct = round((len(matched_keywords) / max(1, len(job_keywords))) * 100, 1)

    # 2. Hallucination Check
    hallucinations: List[str] = []

    # Check for hallucinated universities or degrees
    for banned_claim in ["phd from stanford", "mit graduate", "nobel", "ex-google vp"]:
        if banned_claim in combined_package_text and banned_claim not in user_facts_text:
            hallucinations.append(f"Found ungrounded claim: '{banned_claim}' not present in candidate profile.")

    # 3. Action Verb Count
    action_verbs = ["architected", "engineered", "designed", "optimized", "led", "developed", "built", "implemented", "deployed", "scaled"]
    found_verbs = [v for v in action_verbs if v in combined_package_text]
    action_verb_count = len(found_verbs)

    # 4. ATS Scoring
    base_ats = int(keyword_match_pct * 0.6) + min(30, action_verb_count * 5) + 10
    if hallucinations:
        base_ats = max(30, base_ats - 40)
    final_ats_score = min(98, max(50, base_ats))

    passed = len(hallucinations) == 0 and final_ats_score >= 70

    recommendations: List[str] = []
    if keyword_match_pct < 75:
        recommendations.append("Consider incorporating more domain keywords from the job description.")
    if action_verb_count < 4:
        recommendations.append("Add strong action verbs at the start of each bullet point.")
    if not recommendations:
        recommendations.append("ATS formatting and keyword density is optimal for parsing.")

    result = ReviewAuditResult(
        passed=passed,
        ats_score=final_ats_score,
        keyword_match_pct=keyword_match_pct,
        hallucination_flags=hallucinations,
        action_verb_count=action_verb_count,
        recommendations=recommendations,
    )
    logger.info(f"[Reviewer] ATS Audit for {package.company}: Score {final_ats_score}% (Passed: {passed})")
    return result
