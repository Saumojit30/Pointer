"""
RolePointer — Hacker News 'Who is Hiring' Live Feed Parser
Parses monthly YC / Hacker News hiring posts using the public Firebase HN API.
"""
from __future__ import annotations

import re
from typing import List
import httpx
from loguru import logger

from rolepointer.models.schemas import JobListing, WorkplaceType
from rolepointer.feeds.remote_feeds import _clean_html, _infer_domain


def fetch_hn_hiring_jobs(limit: int = 15) -> List[JobListing]:
    """Scrapes top listings from latest Hacker News 'Who is Hiring' monthly thread."""
    listings: List[JobListing] = []
    try:
        with httpx.Client(timeout=10.0) as client:
            # 1. Search for latest "Who is hiring?" story
            search_res = client.get(
                "https://hn.algolia.com/api/v1/search?tags=story,author_whoishiring&query=Who%20is%20hiring&hitsPerPage=1"
            )
            if search_res.status_code != 200:
                return listings

            hits = search_res.json().get("hits", [])
            if not hits:
                return listings

            story_id = hits[0]["objectID"]
            logger.info(f"[HNFeed] Found latest hiring thread ID: {story_id}")

            # 2. Get comment items
            comments_res = client.get(
                f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&hitsPerPage={limit}"
            )
            if comments_res.status_code != 200:
                return listings

            for comment in comments_res.json().get("hits", []):
                raw_text = comment.get("comment_text", "")
                text = _clean_html(raw_text)
                if len(text) < 60:
                    continue

                # HN standard header format: Company | Role | Location | REMOTE / ONSITE | URL
                first_line = text.split(".")[0].split("\n")[0]
                parts = [p.strip() for p in first_line.split("|")]
                
                company = parts[0] if len(parts) > 0 else "Tech Startup (HN)"
                title = parts[1] if len(parts) > 1 else "Software Engineer"
                loc = parts[2] if len(parts) > 2 else "Remote / US"

                workplace = WorkplaceType.REMOTE if "remote" in text.lower() else (
                    WorkplaceType.HYBRID if "hybrid" in text.lower() else WorkplaceType.ONSITE
                )

                domain = _infer_domain(title, [], text)
                tags = [w for w in ["Python", "FastAPI", "AWS", "React", "TypeScript", "Go", "Kubernetes", "PyTorch", "Rust"] if w.lower() in text.lower()]

                listings.append(JobListing(
                    title=title[:80],
                    company=company[:60],
                    location=loc[:80],
                    workplace_type=workplace,
                    domain=domain,
                    tags=tags,
                    description=text,
                    url=f"https://news.ycombinator.com/item?id={comment.get('objectID')}",
                    source="HackerNews",
                ))

            logger.info(f"[HNFeed] Parsed {len(listings)} hiring comments from Hacker News")
    except Exception as e:
        logger.warning(f"[HNFeed] Hacker News parse error: {e}")
    return listings
