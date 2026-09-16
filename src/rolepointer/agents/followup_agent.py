"""
RolePointer — Response Radar & Value-Add Follow-Up Agent
Monitors outreach lifecycle and generates high-leverage 2-sentence value-add follow-up notes
after 5 days without response (bypasses spam filters with concrete technical insights).
"""
from __future__ import annotations

from typing import List, Optional
from loguru import logger

from rolepointer.models.schemas import JobListing, UserProfile, FollowUpDraft, ApplicationRecord


def generate_value_add_followup(
    job: JobListing,
    profile: UserProfile,
    days_since: int = 5,
    days_since_applied: Optional[int] = None,
    **kwargs
) -> FollowUpDraft:
    """Crafts a 2-sentence value-add follow-up note referencing relevant technical work."""
    effective_days = days_since_applied if days_since_applied is not None else days_since
    tech_focus = job.tags[0] if job.tags else "system architecture"
    second_tech = job.tags[1] if len(job.tags) > 1 else "FastAPI"

    subject = f"Re: {job.title} — Technical Follow-Up & Benchmark Data ({job.company})"
    
    body = (
        f"Hi {job.company} Team,\n\n"
        f"Following up on my note regarding the {job.title} role sent {effective_days} days ago. "
        f"I recently put together an async benchmark comparing {tech_focus} query latency and Redis caching pipelines for high-concurrency endpoints, "
        f"and thought the throughput findings might be directly useful for your current {job.domain} sprint.\n\n"
        f"Happy to share the findings if of interest, or jump on a brief 10-minute technical chat next week.\n\n"
        f"Best regards,\n{profile.name}\n{profile.email} | {profile.phone}"
    )

    talking_point = (
        f"Shares practical benchmark numbers on {tech_focus}/{second_tech} to demonstrate proactive domain mastery without sounding generic or needy."
    )

    draft = FollowUpDraft(
        job_id=job.id,
        company=job.company,
        role=job.title,
        days_since_outreach=effective_days,
        follow_up_strategy="Value-Add Technical Insight",
        subject=subject,
        body=body,
        talking_point=talking_point,
        recommended_action="1-Click Copy & Send Follow-Up",
    )
    logger.info(f"[FollowUpAgent] Generated value-add follow-up for {job.title} @ {job.company} (Day {effective_days})")
    return draft
