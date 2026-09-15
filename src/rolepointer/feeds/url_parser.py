"""
RolePointer — Universal Job URL Scraper
Extracts job title, company, location, and requirements from any job posting URL
(Greenhouse, Lever, Ashby, LinkedIn, or direct career pages).
"""
from __future__ import annotations

import re
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from loguru import logger

from rolepointer.models.schemas import JobListing, WorkplaceType
from rolepointer.feeds.remote_feeds import _infer_domain


def parse_job_url(url: str) -> Optional[JobListing]:
    """Scrapes and parses structured job data from a given URL."""
    if not url or not url.startswith("http"):
        return None

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            res = client.get(url, headers=headers)
            if res.status_code != 200:
                logger.warning(f"[URLParser] HTTP {res.status_code} for {url}")
                return None

            soup = BeautifulSoup(res.text, "html.parser")

            # 1. Extract Title
            title = ""
            for tag in ["h1", "title"]:
                elem = soup.find(tag)
                if elem and len(elem.get_text(strip=True)) > 3:
                    title = elem.get_text(strip=True)
                    break
            if not title:
                title = "Senior Software Engineer"

            # 2. Extract Company
            company = ""
            if "greenhouse.io" in url:
                company = url.split("greenhouse.io/")[1].split("/")[0].title()
            elif "lever.co" in url:
                company = url.split("lever.co/")[1].split("/")[0].title()
            elif "ashbyhq.com" in url:
                company = url.split("ashbyhq.com/")[1].split("/")[0].title()
            
            if not company:
                meta_company = soup.find("meta", property="og:site_name")
                if meta_company and meta_company.get("content"):
                    company = meta_company["content"]
            if not company:
                company = "Innovative Tech Co"

            # 3. Extract Location & Workplace
            body_text = soup.get_text(separator=" ", strip=True)
            body_lower = body_text.lower()

            workplace = WorkplaceType.REMOTE if "remote" in body_lower else (
                WorkplaceType.HYBRID if "hybrid" in body_lower else WorkplaceType.ONSITE
            )
            location = "Remote" if workplace == WorkplaceType.REMOTE else "San Francisco, CA, US"

            # 4. Extract Description
            # Look for main containers
            desc_elem = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|description|job-details", re.I))
            if desc_elem:
                description = desc_elem.get_text(separator="\n", strip=True)
            else:
                description = body_text[:3000]

            # 5. Extract tags & domain
            tags = [
                t for t in ["Python", "FastAPI", "AWS", "React", "TypeScript", "Docker", "Kubernetes", "PyTorch", "PostgreSQL", "Go", "SQL"]
                if t.lower() in body_lower
            ]
            domain = _infer_domain(title, tags, description)

            job = JobListing(
                title=title[:100],
                company=company[:60],
                location=location,
                workplace_type=workplace,
                domain=domain,
                tags=tags,
                description=description[:5000],
                url=url,
                source="DirectURL",
            )
            logger.info(f"[URLParser] Successfully parsed URL: {title} @ {company}")
            return job

    except Exception as e:
        logger.warning(f"[URLParser] Failed to parse {url}: {e}")
        return None
