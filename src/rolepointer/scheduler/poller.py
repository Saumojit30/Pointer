"""
RolePointer — Autonomous Background Feed Poller & Discovery Scheduler
Periodically scans live remote, location, and HN feeds, filters duplicates,
evaluates fit against candidate guardrails, persists to DB, and broadcasts SSE alerts.
"""
from __future__ import annotations

import asyncio
import hashlib
from typing import Callable, Dict, List, Optional
from loguru import logger

from rolepointer.models.schemas import JobListing, UserProfile, FitEvaluation
from rolepointer.feeds.remote_feeds import fetch_jobicy_jobs, fetch_remoteok_jobs
from rolepointer.feeds.location_feeds import fetch_arbeitnow_jobs
from rolepointer.feeds.hn_hiring_feed import fetch_hn_hiring_jobs
from rolepointer.agents.fit_evaluator import evaluate_job_fit
from rolepointer.db.repository import save_job


def _make_job_signature(job: JobListing) -> str:
    raw = f"{job.company.lower().strip()}|{job.title.lower().strip()}|{job.url.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


async def run_discovery_cycle(
    profile: UserProfile,
    jobs_store: Dict[str, JobListing],
    evaluations_store: Dict[str, FitEvaluation],
    sse_queue: Optional[asyncio.Queue] = None,
) -> int:
    """
    Executes a single discovery cycle across all feeds with error isolation and deduplication.
    Returns the count of newly discovered jobs.
    """
    logger.info("[Scheduler] Starting autonomous discovery cycle across live feeds...")
    discovered_jobs: List[JobListing] = []

    # 1. Jobicy
    try:
        j_jobs = await fetch_jobicy_jobs(count=15)
        discovered_jobs.extend(j_jobs)
        logger.info(f"[Scheduler] Fetched {len(j_jobs)} jobs from Jobicy")
    except Exception as e:
        logger.warning(f"[Scheduler] Jobicy fetch skipped: {e}")

    # 2. RemoteOK
    try:
        r_jobs = await fetch_remoteok_jobs(count=15)
        discovered_jobs.extend(r_jobs)
        logger.info(f"[Scheduler] Fetched {len(r_jobs)} jobs from RemoteOK")
    except Exception as e:
        logger.warning(f"[Scheduler] RemoteOK fetch skipped: {e}")

    # 3. Arbeitnow
    try:
        a_jobs = await fetch_arbeitnow_jobs(count=15)
        discovered_jobs.extend(a_jobs)
        logger.info(f"[Scheduler] Fetched {len(a_jobs)} jobs from Arbeitnow")
    except Exception as e:
        logger.warning(f"[Scheduler] Arbeitnow fetch skipped: {e}")

    # 4. Hacker News "Who is Hiring?"
    try:
        h_jobs = await fetch_hn_hiring_jobs(count=10)
        discovered_jobs.extend(h_jobs)
        logger.info(f"[Scheduler] Fetched {len(h_jobs)} jobs from Hacker News")
    except Exception as e:
        logger.warning(f"[Scheduler] Hacker News fetch skipped: {e}")

    # Build signature set of existing jobs to prevent duplicates
    existing_signatures = {_make_job_signature(j) for j in jobs_store.values()}
    new_count = 0

    for job in discovered_jobs:
        sig = _make_job_signature(job)
        if sig in existing_signatures or job.id in jobs_store:
            continue

        existing_signatures.add(sig)
        new_count += 1

        # Evaluate fit against candidate guardrails
        eval_res = evaluate_job_fit(job, profile)
        
        # Store in-memory
        jobs_store[job.id] = job
        evaluations_store[job.id] = eval_res

        # Persist to database
        try:
            save_job(job, eval_res)
        except Exception as e:
            logger.error(f"[Scheduler] Failed to persist job {job.id}: {e}")

        # Broadcast high-fit alerts via SSE
        if eval_res.score >= 85 and not eval_res.has_dealbreaker and sse_queue is not None:
            try:
                await sse_queue.put({
                    "event": "high_fit_match",
                    "data": {
                        "job_id": job.id,
                        "company": job.company,
                        "title": job.title,
                        "score": eval_res.score,
                        "match_tier": eval_res.match_tier,
                        "domain": job.domain,
                    }
                })
                logger.info(f"[Scheduler] Broadcasted high-fit match: {job.company} - {job.title} ({eval_res.score}%)")
            except Exception as e:
                logger.warning(f"[Scheduler] SSE broadcast failed: {e}")

    logger.info(f"[Scheduler] Discovery cycle complete: {new_count} new opportunities added.")
    return new_count


async def background_poller_loop(
    profile_getter: Callable[[], UserProfile],
    jobs_store: Dict[str, JobListing],
    evaluations_store: Dict[str, FitEvaluation],
    sse_queue: asyncio.Queue,
    interval_seconds: int = 1800,  # default: 30 minutes
) -> None:
    """Long-running background poller daemon."""
    logger.info(f"[Scheduler] Background poller daemon started (interval: {interval_seconds}s)")
    while True:
        try:
            profile = profile_getter()
            await run_discovery_cycle(profile, jobs_store, evaluations_store, sse_queue)
        except asyncio.CancelledError:
            logger.info("[Scheduler] Background poller daemon cancelled.")
            break
        except Exception as e:
            logger.error(f"[Scheduler] Error in poller loop: {e}")

        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            break
