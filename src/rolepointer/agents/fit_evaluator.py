"""
RolePointer — Fit Evaluator Agent & Dealbreaker Sentinel
Scores job listings against user profile (0-100%), extracts pros/cons,
and flags dealbreaker violations (salary floor, on-call, crypto, legacy tech,
ghost job signatures, work authorization mismatches, and timezone overlap).
"""
from __future__ import annotations

import re
from typing import List, Tuple
from loguru import logger

from rolepointer.models.schemas import (
    JobListing, UserProfile, FitEvaluation, DealbreakerAlert, WorkplaceType,
    GhostRiskLevel
)
from rolepointer.feeds.salary_normalizer import normalize_compensation
from rolepointer.feeds.link_and_ghost_verifier import detect_ghost_job
from rolepointer.feeds.work_auth_filter import evaluate_work_auth_and_timezone
from rolepointer.core.model_config import generate_llm_response


def evaluate_job_fit(job: JobListing, profile: UserProfile) -> FitEvaluation:
    """
    Evaluates role fit against user profile with positive stack match, dealbreaker check,
    multi-currency salary normalization, anti-ghost job heuristics, and work authorization.
    """
    user_skills_lower = [s.lower() for s in profile.skills]
    job_text = f"{job.title} {job.description} {' '.join(job.tags)}".lower()

    # 1. Multi-Currency Salary Normalization
    salary_norm = normalize_compensation(job.salary_range)

    # 2. Anti-Ghost Job Heuristics
    ghost_verdict = detect_ghost_job(job)

    # 3. Work Authorization & Timezone Overlap
    work_auth_verdict = evaluate_work_auth_and_timezone(job, profile)

    # 4. Dealbreaker Analysis
    dealbreaker_alerts: List[DealbreakerAlert] = []
    has_dealbreaker = False

    # A. Check against salary floor using normalized USD
    effective_max_salary = (
        salary_norm.annual_max_usd
        if salary_norm.annual_max_usd is not None and salary_norm.annual_max_usd > 0
        else job.salary_max
    )

    for rule in profile.dealbreakers:
        r_clean = rule.strip().lower()
        if not r_clean:
            continue

        if "salary" in r_clean or "floor" in r_clean:
            if profile.min_salary_floor and effective_max_salary and effective_max_salary < profile.min_salary_floor:
                dealbreaker_alerts.append(DealbreakerAlert(
                    rule=rule,
                    triggered=True,
                    explanation=f"Normalized max salary (${effective_max_salary:,.0f} USD/yr) is below your floor (${profile.min_salary_floor:,.0f})."
                ))
                has_dealbreaker = True
                continue

        # Check keyword/phrase in job text
        phrases_to_check = [r_clean] if " " in r_clean else [k.strip() for k in r_clean.replace("/", " ").split() if len(k.strip()) > 3]
        for kw in phrases_to_check:
            pattern = r"(?<!no\s)(?<!without\s)\b" + re.escape(kw) + r"\b"
            if re.search(pattern, job_text):
                dealbreaker_alerts.append(DealbreakerAlert(
                    rule=rule,
                    triggered=True,
                    explanation=f"Explicitly mentions '{kw}', violating your '{rule}' preference."
                ))
                has_dealbreaker = True
                break

    # B. Work Auth Dealbreaker Check
    if not work_auth_verdict.compatible:
        dealbreaker_alerts.append(DealbreakerAlert(
            rule="Work Authorization / Geography",
            triggered=True,
            explanation=work_auth_verdict.explanation,
        ))
        has_dealbreaker = True

    # 5. Skill Match & Gaps
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

    # 6. Score Calculation
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

    # Ghost Job Penalty
    if ghost_verdict.is_ghost_job or ghost_verdict.risk_level == GhostRiskLevel.HIGH_GHOST_RISK:
        base_score = max(10, base_score - 25)
    elif ghost_verdict.risk_level == GhostRiskLevel.MODERATE_RISK:
        base_score = max(10, base_score - 10)

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

    # 7. Pros & Cons Synthesis
    pros: List[str] = []
    cons: List[str] = []

    if matching_skills:
        pros.append(f"Strong tech stack overlap: {', '.join(matching_skills[:4])}")
    if job.workplace_type == WorkplaceType.REMOTE:
        pros.append(f"100% remote ({work_auth_verdict.timezone_overlap_hours}h daily UTC overlap).")
    elif job.city and any(c.lower() in job.city.lower() for c in profile.city_preference):
        pros.append(f"Located in target hub ({job.city}).")

    if salary_norm.confidence != "NONE":
        pros.append(f"Standardized comp: {salary_norm.formatted_usd_equiv}")

    if ghost_verdict.risk_level == GhostRiskLevel.LOW_RISK:
        pros.append("Verified active posting (Low ghost risk).")

    if missing_skills:
        cons.append(f"Requires familiarity with {', '.join(missing_skills[:3])}.")
    if ghost_verdict.warning_flags:
        cons.append(f"Ghost risk: {ghost_verdict.warning_flags[0]}")
    if has_dealbreaker:
        cons.append("Contains candidate criteria exclusions or work auth barrier.")
    if salary_norm.confidence == "NONE" and not job.salary_range:
        cons.append("Salary range not disclosed upfront in job posting.")

    summary = (
        f"{match_tier} Fit ({final_score}%): {job.title} at {job.company}. "
        f"Matches {len(matching_skills)} core skills. Comp: {salary_norm.formatted_usd_equiv}. "
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
        ghost_verdict=ghost_verdict,
        salary_normalized=salary_norm,
        work_auth_verdict=work_auth_verdict,
    )
    logger.info(f"[FitEvaluator] Evaluated {job.title} @ {job.company} -> Score: {final_score}% ({match_tier})")
    return evaluation
