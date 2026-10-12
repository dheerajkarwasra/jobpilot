"""Arbeitnow public job board API (Germany focused, English friendly). No key needed.

Docs: https://www.arbeitnow.com/api/job-board-api
"""
from __future__ import annotations

from typing import List

from ..models import Job
from .base import strip_html, to_date

URL = "https://www.arbeitnow.com/api/job-board-api"


def fetch(ctx) -> List[Job]:
    pages = int(ctx.ws.get("sources.arbeitnow_pages", 5))
    jobs: List[Job] = []
    for page in range(1, pages + 1):
        data = ctx.http.get_json(URL, params={"page": page})
        items = data.get("data") or []
        if not items:
            break
        for it in items:
            slug = str(it.get("slug") or "")
            remote = it.get("remote")
            jobs.append(Job(
                title=str(it.get("title") or "").strip(),
                company=str(it.get("company_name") or "").strip(),
                link=str(it.get("url") or ""),
                source="Arbeitnow",
                location=str(it.get("location") or ""),
                description=strip_html(it.get("description")),
                posted_date=to_date(it.get("created_at")),
                posting_ref=f"AN-{slug.rsplit('-', 1)[-1]}" if slug else "",
                employment_hint=" ".join(it.get("job_types") or []),
                remote_hint=bool(remote) if remote is not None else None,
            ))
        links = data.get("links")
        if isinstance(links, dict) and "next" in links and not links["next"]:
            break
    return jobs
