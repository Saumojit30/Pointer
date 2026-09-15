"""
RolePointer — Executive Daily Briefing & Auto-Precompilation Agent
Eliminates 100-job scrolling fatigue by autonomously curating the Top 3-5 high-fit roles
and pre-compiling their tailored ATS packages in the background.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple
from loguru import logger

from rolepointer.models.schemas import (
    JobListing, UserProfile, FitEvaluation, TailoredPackage, ExecutiveBriefing
)
from rolepointer.agents.fit_evaluator import evaluate_job_fit
from rolepointer.agents.drafter import draft_tailored_package
from rolepointer.agents.reviewer import audit_tailored_package
from rolepointer.compiler.pdf_engine import compile_ats_resume_pdf


def generate_executive_briefing(
    jobs: List[JobListing],
    profile: UserProfile,
    packages_store: Dict[str, TailoredPackage],
    top_limit: int = 3,
) -> Tuple[ExecutiveBriefing, List[TailoredPackage]]:
    """Curates the Top 3 daily roles and auto-precompiles their packages in the background."""
    today_str = datetime.now().strftime("%A, %B %d, %Y")
    
    # 1. Evaluate all jobs and filter out any with criteria mismatches
    qualified: List[Tuple[JobListing, FitEvaluation]] = []
    for job in jobs:
        ev = evaluate_job_fit(job, profile)
        if not ev.has_dealbreaker and ev.score >= 70:
            qualified.append((job, ev))

    # 2. Sort descending by score
    qualified.sort(key=lambda item: item[1].score, reverse=True)
    top_items = qualified[:top_limit]

    top_jobs = [item[0] for item in top_items]
    top_evals = [item[1] for item in top_items]

    # 3. Autonomous Background Pre-Compilation for Top Roles
    precompiled: List[TailoredPackage] = []
    for job in top_jobs:
        if job.id not in packages_store:
            pkg = draft_tailored_package(job, profile)
            audit = audit_tailored_package(pkg, job, profile)
            pkg.audit_result = audit
            pdf_name = compile_ats_resume_pdf(pkg, profile)
            pkg.pdf_filename = pdf_name
            packages_store[job.id] = pkg
            precompiled.append(pkg)
            logger.info(f"[BriefingAgent] Pre-compiled application package for {job.company} ({job.title})")
        else:
            precompiled.append(packages_store[job.id])

    # 4. Generate Executive Synthesis Summary
    avg_score = int(sum(ev.score for ev in top_evals) / max(1, len(top_evals))) if top_evals else 0
    names = ", ".join([j.company for j in top_jobs[:3]]) if top_jobs else "None"
    
    summary = (
        f"Good morning, {profile.name.split()[0]}. Overnight discovery scoured {len(jobs)} total listings. "
        f"We identified {len(top_jobs)} tier-one opportunities ({names}) with an average compatibility of {avg_score}%. "
        f"All {len(precompiled)} bespoke ATS resume packages and 4-sentence direct pitches are pre-compiled and ready for your 1-click review."
    )

    briefing = ExecutiveBriefing(
        date=today_str,
        greeting=f"Executive Morning Briefing — {today_str}",
        total_scoured=len(jobs),
        qualified_count=len(qualified),
        top_opportunities=top_jobs,
        top_evaluations=top_evals,
        precompiled_packages=precompiled,
        executive_summary=summary,
    )
    logger.info(f"[BriefingAgent] Daily Executive Briefing generated: {len(top_jobs)} curated roles")
    return briefing, precompiled
