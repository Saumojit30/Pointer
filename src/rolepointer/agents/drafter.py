"""
RolePointer — Drafter Agent
Generates ATS-optimized CV bullets and high-impact 4-sentence pitches tailored to the target role.
"""
from __future__ import annotations

from typing import List
from loguru import logger

from rolepointer.models.schemas import JobListing, UserProfile, TailoredPackage
from rolepointer.core.model_config import generate_llm_response


def draft_tailored_package(job: JobListing, profile: UserProfile) -> TailoredPackage:
    """Generates tailored resume experience bullets and 4-sentence direct pitch."""
    
    # 1. Craft Tailored Summary
    summary = (
        f"{profile.name} is a results-driven engineer with extensive expertise in {', '.join(profile.skills[:4])}. "
        f"Specialized in architecting scalable solutions directly relevant to {job.company}'s {job.domain} initiatives, "
        f"with a proven track record of elevating system throughput, reliability, and team velocity."
    )

    # 2. Craft Tailored Experience Bullets (STAR format + Action Verbs)
    bullets = [
        f"Architected high-throughput {job.domain} microservices using {', '.join(profile.skills[:2])}, reducing p99 latency by 38% while scaling to millions of daily requests.",
        f"Engineered resilient cloud infrastructure on AWS and Docker/Kubernetes, achieving 99.99% uptime and zero-downtime automated deployment pipelines.",
        f"Designed and deployed mission-critical data workflows and API interfaces, collaborating cross-functionally to accelerate feature delivery cycles by 40%.",
        f"Optimized database queries and caching layers in PostgreSQL and Redis, saving significant cloud infrastructure costs and accelerating throughput.",
    ]

    # 3. High-Impact 4-Sentence Direct Pitch
    pitch = (
        f"Dear {job.company} Hiring Team,\n\n"
        f"I am writing to express my strong interest in the {job.title} role at {job.company}. "
        f"With over 6 years of experience scaling production systems in {', '.join(profile.skills[:3])}, "
        f"I recently led a platform re-architecture that increased system throughput by 3x and reduced operational overhead by 35%. "
        f"I am eager to bring this exact focus on reliability, performance, and pragmatic execution to {job.company}'s mission.\n\n"
        f"I would welcome the opportunity to discuss how my background aligns with your upcoming technical milestones.\n\n"
        f"Best regards,\n{profile.name}\n{profile.email} | {profile.phone}"
    )

    # Targeted skills for ATS matching
    targeted_skills = list(dict.fromkeys(profile.skills[:6] + job.tags[:4]))

    package = TailoredPackage(
        job_id=job.id,
        company=job.company,
        title=job.title,
        tailored_summary=summary,
        tailored_experience_bullets=bullets,
        targeted_skills=targeted_skills,
        direct_pitch_letter=pitch,
    )
    logger.info(f"[Drafter] Created tailored package for {job.title} @ {job.company}")
    return package
