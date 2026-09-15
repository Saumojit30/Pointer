"""
RolePointer — Location-Specific & Onsite Job Feeds
Fetches country/city jobs from Arbeitnow and global city filters (US, UK, Germany, India).
"""
from __future__ import annotations

import re
from typing import List, Optional
import httpx
from loguru import logger

from rolepointer.models.schemas import JobListing, WorkplaceType
from rolepointer.feeds.remote_feeds import _clean_html, _infer_domain


def fetch_arbeitnow_jobs(count: int = 20) -> List[JobListing]:
    """Fetch location-tagged and hybrid/onsite jobs from Arbeitnow API."""
    url = "https://www.arbeitnow.com/api/job-board-api"
    listings: List[JobListing] = []
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(url, headers={"User-Agent": "RolePointer/1.0"})
            if res.status_code == 200:
                data = res.json()
                for item in data.get("data", [])[:count]:
                    title = item.get("title", "")
                    company = item.get("company_name", "")
                    location = item.get("location", "Berlin, Germany")
                    remote_flag = item.get("remote", False)
                    desc = _clean_html(item.get("description", ""))
                    job_url = item.get("url", "https://arbeitnow.com")
                    tags = item.get("tags", [])
                    
                    # Infer country & city
                    country = "Germany"
                    city = "Berlin"
                    if "," in location:
                        parts = [p.strip() for p in location.split(",")]
                        city = parts[0]
                        country = parts[-1]
                    elif "Remote" in location:
                        country = "Worldwide"
                        city = "Remote"

                    workplace_type = WorkplaceType.REMOTE if remote_flag else (
                        WorkplaceType.HYBRID if "hybrid" in desc.lower() or "hybrid" in location.lower() else WorkplaceType.ONSITE
                    )
                    domain = _infer_domain(title, tags, desc)

                    listings.append(JobListing(
                        title=title,
                        company=company,
                        location=location,
                        country=country,
                        city=city,
                        workplace_type=workplace_type,
                        domain=domain,
                        tags=tags[:8],
                        description=desc,
                        url=job_url,
                        source="Arbeitnow",
                    ))
                logger.info(f"[LocationFeeds] Fetched {len(listings)} jobs from Arbeitnow")
    except Exception as e:
        logger.warning(f"[LocationFeeds] Arbeitnow feed error: {e}")
    return listings


def filter_by_location(
    jobs: List[JobListing],
    target_countries: Optional[List[str]] = None,
    target_cities: Optional[List[str]] = None,
    workplace_types: Optional[List[WorkplaceType]] = None,
) -> List[JobListing]:
    """Filters job list by country, city, and workplace type."""
    if not jobs:
        return []

    filtered = []
    for j in jobs:
        # Workplace type match
        if workplace_types and WorkplaceType.ANY not in workplace_types:
            if j.workplace_type not in workplace_types:
                continue

        # Country match
        if target_countries and j.country and j.country != "Worldwide":
            country_matched = any(c.lower() in j.country.lower() or j.country.lower() in c.lower() for c in target_countries)
            if not country_matched:
                continue

        # City match
        if target_cities and j.city and j.city != "Remote":
            city_matched = any(c.lower() in j.city.lower() or j.city.lower() in c.lower() for c in target_cities)
            if not city_matched:
                continue

        filtered.append(j)
    return filtered
