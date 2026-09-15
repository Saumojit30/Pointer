"""
RolePointer — Fit Evaluator Agent & Dealbreaker Sentinel
Scores job listings against user profile (0-100%), extracts pros/cons,
and flags dealbreaker violations (salary floor, on-call, crypto, legacy tech).
"""
from __future__ import annotations

import re
from typing import List, Tuple
from loguru import logger

from rolepointer.models.schemas import (
    JobListing, UserProfile, FitEvaluation, DealbreakerAlert, WorkplaceType
)
from rolepointer.core.model_config import generate_llm_response


def evaluate_job_fit(job: JobListing, profile: UserProfile) -> FitEvaluation:
    """Evaluates role fit against user profile with positive stack match & dealbreaker check."""
    user_skills_lower = [s.lower() for s in profile.skills]
    job_text = f"{job.title} {job.description} {' '.join(job.tags)}".lower()

    # 1. Dealbreaker Analysis
    dealbreaker_alerts: List[DealbreakerAlert] = []
    has_dealbreaker = False

    for rule in profile.dealbreakers:
        r_clean = rule.strip().lower()
        if not r_clean:
            continue
        
        # Check against salary floor
        if "salary" in r_clean or "floor" in r_clean:
            if profile.min_salary_floor and job.salary_max and job.salary_max < profile.min_salary_floor:
                dealbreaker_alerts.append(DealbreakerAlert(
                    rule=rule,
                    triggered=True,
                    explanation=f"Max salary (${job.salary_max:,.0f}) is below your floor (${profile.min_salary_floor:,.0f})."
                ))
                has_dealbreaker = True
                continue

        # Check keyword/phrase in job text
        phrases_to_check = [r_clean] if " " in r_clean else [k.strip() for k in r_clean.replace("/", " ").split() if len(k.strip()) > 3]
        for kw in phrases_to_check:
            # Check for non-negated match
            pattern = r"(?<!no\s)(?<!without\s)\b" + re.escape(kw) + r"\b"
            if re.search(pattern, job_text):
                dealbreaker_alerts.append(DealbreakerAlert(
                    rule=rule,
                    triggered=True,
                    explanation=f"Explicitly mentions '{kw}', violating your '{rule}' preference."
                ))
                has_dealbreaker = True
                break

    # 2. Skill Match & Gaps
    matching_skills: List[str] = []
    missing_skills: List[str] = []

    for tag in job.tags:
        if tag.lower() in user_skills_lower:
            matching_skills.append(tag)
        else:
            missing_skills.append(tag)

    for skill in profile.skills:
        if re.search(r"\b" + re.escape(skill.lower()) + r"\b", job_text) and skill not in matching_skills:
            matching_skills.append(skill)

    # 3. Score Calculation
    base_score = 40

    # Domain bonus
    if any(d.lower() in job.domain.lower() for d in profile.target_domains):
        base_score += 20

    # Skill match score
    skill_ratio = len(matching_skills) / max(1, (len(matching_skills) + len(missing_skills[:5])))
    base_score += int(skill_ratio * 30)

    # Workplace preference match
    if job.workplace_type in profile.preferred_workplace_types or WorkplaceType.ANY in profile.preferred_workplace_types:
        base_score += 10

    # Dealbreaker penalty
    if has_dealbreaker:
        base_score = max(15, base_score - 45)

    final_score = min(98, max(10, base_score))

    # Tier
    if final_score >= 85:
        match_tier = "EXCELLENT"
    elif final_score >= 70:
        match_tier = "STRONG"
    elif final_score >= 50:
        match_tier = "MODERATE"
    else:
        match_tier = "POOR"

    # 4. Pros & Cons Synthesis
    pros: List[str] = []
    cons: List[str] = []

    if matching_skills:
        pros.append(f"Strong tech stack overlap: {', '.join(matching_skills[:4])}")
    if job.workplace_type == WorkplaceType.REMOTE:
        pros.append("100% remote flexibility matches target profile.")
    elif job.city and any(c.lower() in job.city.lower() for c in profile.city_preference):
        pros.append(f"Located in target hub ({job.city}).")
    if job.salary_range:
        pros.append(f"Transparent compensation offered ({job.salary_range}).")

    if missing_skills:
        cons.append(f"Requires familiarity with {', '.join(missing_skills[:3])}.")
    if has_dealbreaker:
        cons.append("Contains candidate criteria exclusions.")
    if not job.salary_range:
        cons.append("Salary range not disclosed upfront in job posting.")

    summary = (
        f"{match_tier} Fit ({final_score}%): {job.title} at {job.company}. "
        f"Matches {len(matching_skills)} of your core competencies. "
        + ("⚠️ Has criteria alignment notices." if has_dealbreaker else "✓ Clears all alignment guardrails.")
    )

    evaluation = FitEvaluation(
        job_id=job.id,
        score=final_score,
        match_tier=match_tier,
        pros=pros[:3],
        cons=cons[:3],
        dealbreaker_alerts=dealbreaker_alerts,
        has_dealbreaker=has_dealbreaker,
        matching_skills=matching_skills[:6],
        missing_skills=missing_skills[:4],
        summary=summary,
    )
    logger.info(f"[FitEvaluator] Evaluated {job.title} @ {job.company} -> Score: {final_score}% ({match_tier})")
    return evaluation
