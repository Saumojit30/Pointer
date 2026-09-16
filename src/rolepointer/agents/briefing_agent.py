"""
RolePointer — Executive Daily Briefing & Auto-Precompilation Agent
Eliminates 100-job scrolling fatigue by autonomously curating the Top 3-5 high-fit roles
and pre-compiling their tailored ATS packages in the background.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

from rolepointer.models.schemas import (
    JobListing, UserProfile, FitEvaluation, TailoredPackage, ExecutiveBriefing
)
from rolepointer.agents.fit_evaluator import evaluate_job_fit
from rolepointer.agents.drafter import draft_tailored_package
from rolepointer.agents.reviewer import audit_tailored_package
from rolepointer.compiler.pdf_engine import compile_ats_resume_pdf


def generate_executive_briefing(
    jobs: Optional[List[JobListing]] = None,
    profile: Optional[UserProfile] = None,
    packages_store: Optional[Dict[str, TailoredPackage]] = None,
    all_jobs: Optional[List[JobListing]] = None,
    top_limit: int = 3,
    **kwargs
) -> ExecutiveBriefing:
    """Curates the Top 3 daily roles and auto-precompiles their packages in the background."""
    job_list = jobs if jobs is not None else (all_jobs or [])
    user_prof = profile or UserProfile()
    pkg_store = packages_store if packages_store is not None else {}

    today_str = datetime.now().strftime("%A, %B %d, %Y")
    
    # 1. Evaluate all jobs and filter out any with criteria mismatches
    qualified = []
    for job in job_list:
        ev = evaluate_job_fit(job, user_prof)
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
        if job.id not in pkg_store:
            pkg = draft_tailored_package(job, user_prof)
            audit = audit_tailored_package(pkg, job, user_prof)
            pkg.audit_result = audit
            pdf_name = compile_ats_resume_pdf(pkg, user_prof)
            pkg.pdf_filename = pdf_name
            pkg_store[job.id] = pkg
            precompiled.append(pkg)
            logger.info(f"[BriefingAgent] Pre-compiled application package for {job.company} ({job.title})")
        else:
            precompiled.append(pkg_store[job.id])

    # 4. Generate Executive Synthesis Summary
    avg_score = int(sum(ev.score for ev in top_evals) / max(1, len(top_evals))) if top_evals else 0
    names = ", ".join([j.company for j in top_jobs[:3]]) if top_jobs else "None"
    
    greeting = f"Good morning, {user_prof.name.split()[0]} — Executive Briefing ({today_str})"
    summary = (
        f"Executive Morning Briefing: Good morning, {user_prof.name.split()[0]}. Overnight discovery scoured {len(job_list)} total listings. "
        f"We identified {len(top_jobs)} tier-one opportunities ({names}) with an average compatibility of {avg_score}%. "
        f"All {len(precompiled)} bespoke ATS resume packages and 4-sentence direct pitches are pre-compiled and ready for your 1-click review."
    )

    briefing = ExecutiveBriefing(
        date=today_str,
        greeting=greeting,
        total_scoured=len(job_list),
        qualified_count=len(qualified),
        top_opportunities=top_jobs,
        top_evaluations=top_evals,
        precompiled_packages=precompiled,
        executive_summary=summary,
    )
    logger.info(f"[BriefingAgent] Daily Executive Briefing generated: {len(top_jobs)} curated roles")
    return briefing
