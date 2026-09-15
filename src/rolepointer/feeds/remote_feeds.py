"""
RolePointer — Remote Feed Connectors
Ingests live remote jobs from Jobicy, RemoteOK, and public API feeds.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List
import httpx
from loguru import logger

from rolepointer.models.schemas import JobListing, WorkplaceType, ExperienceLevel


def _clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def _infer_domain(title: str, tags: List[str], description: str) -> str:
    text = f"{title} {' '.join(tags)} {description[:300]}".lower()
    if any(k in text for k in ["ai", "machine learning", "llm", "deep learning", "pytorch", "nlp", "computer vision"]):
        return "AI/ML"
    if any(k in text for k in ["devops", "cloud", "kubernetes", "terraform", "sre", "infrastructure"]):
        return "DevOps/Cloud"
    if any(k in text for k in ["data engineer", "data pipeline", "spark", "dbt", "snowflake"]):
        return "Data Engineering"
    if any(k in text for k in ["frontend", "react", "vue", "next.js", "tailwind", "ui"]):
        return "Frontend"
    if any(k in text for k in ["fullstack", "full stack", "full-stack"]):
        return "Fullstack"
    if any(k in text for k in ["product manager", "product lead"]):
        return "Product"
    return "Backend"


def fetch_jobicy_jobs(industry: str = "engineering", count: int = 15) -> List[JobListing]:
    """Fetch remote jobs from Jobicy public API."""
    url = f"https://jobicy.com/api/v2/remote-jobs?count={count}&industry={industry}"
    listings: List[JobListing] = []
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(url, headers={"User-Agent": "RolePointer-CareerAgent/1.0"})
            if res.status_code == 200:
                data = res.json()
                for item in data.get("jobs", []):
                    title = item.get("jobTitle", "Software Engineer")
                    company = item.get("companyName", "Tech Company")
                    desc = _clean_html(item.get("jobDescription", ""))
                    job_url = item.get("url", "https://jobicy.com")
                    tags = item.get("jobSkills", [])
                    if isinstance(tags, str):
                        tags = [t.strip() for t in tags.split(",") if t.strip()]
                    
                    domain = _infer_domain(title, tags, desc)
                    listings.append(JobListing(
                        title=title,
                        company=company,
                        location="Remote (Worldwide)",
                        country="Worldwide",
                        workplace_type=WorkplaceType.REMOTE,
                        domain=domain,
                        tags=tags[:8],
                        description=desc,
                        url=job_url,
                        source="Jobicy",
                    ))
                logger.info(f"[RemoteFeeds] Fetched {len(listings)} jobs from Jobicy")
    except Exception as e:
        logger.warning(f"[RemoteFeeds] Jobicy feed error: {e}")
    return listings


def fetch_remoteok_jobs(count: int = 15) -> List[JobListing]:
    """Fetch remote developer jobs from RemoteOK public feed."""
    url = "https://remoteok.com/api"
    listings: List[JobListing] = []
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(url, headers={"User-Agent": "Mozilla/5.0 (RolePointer Career Bot)"})
            if res.status_code == 200:
                data = res.json()
                for item in data[1:count+1]:  # Index 0 is legal notice
                    title = item.get("position", "")
                    company = item.get("company", "")
                    if not title or not company:
                        continue
                    desc = _clean_html(item.get("description", ""))
                    job_url = item.get("url", f"https://remoteok.com/l/{item.get('id', '')}")
                    tags = item.get("tags", [])
                    domain = _infer_domain(title, tags, desc)
                    
                    listings.append(JobListing(
                        title=title,
                        company=company,
                        location=item.get("location", "Remote"),
                        country="Worldwide",
                        workplace_type=WorkplaceType.REMOTE,
                        domain=domain,
                        salary_min=float(item.get("salary_min")) if item.get("salary_min") else None,
                        salary_max=float(item.get("salary_max")) if item.get("salary_max") else None,
                        tags=tags[:8],
                        description=desc,
                        url=job_url,
                        source="RemoteOK",
                    ))
                logger.info(f"[RemoteFeeds] Fetched {len(listings)} jobs from RemoteOK")
    except Exception as e:
        logger.warning(f"[RemoteFeeds] RemoteOK feed error: {e}")
    return listings
