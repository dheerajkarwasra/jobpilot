"""Adzuna job search API. Free developer key: https://developer.adzuna.com/
Covers DE, AT, CH, NL, FR, UK, US, IN and more. Set JOBPILOT_ADZUNA_APP_ID and
JOBPILOT_ADZUNA_APP_KEY in the workspace .env.
"""
from __future__ import annotations

from typing import List

from ..models import Job
from .base import SourceError, strip_html, to_date

URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def fetch(ctx) -> List[Job]:
    app_id = ctx.ws.env.get("JOBPILOT_ADZUNA_APP_ID")
    app_key = ctx.ws.env.get("JOBPILOT_ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise SourceError("Adzuna keys missing (JOBPILOT_ADZUNA_APP_ID / JOBPILOT_ADZUNA_APP_KEY)")
    country = ctx.ws.country.get("adzuna") or ctx.ws.get("search.country", "de")
    jobs: List[Job] = []
    for q in ctx.all_queries:
        params = {"app_id": app_id, "app_key": app_key, "what": q, "max_days_old": ctx.max_age_days,
                  "results_per_page": 50, "sort_by": "date", "content-type": "application/json"}
        data = ctx.http.get_json(URL.format(country=country, page=1), params=params)
        for it in data.get("results") or []:
            jid = str(it.get("id") or "")
            jobs.append(Job(
                title=strip_html(it.get("title")),
                company=str((it.get("company") or {}).get("display_name") or "").strip(),
                link=str(it.get("redirect_url") or ""),
                source="Adzuna",
                location=str((it.get("location") or {}).get("display_name") or ""),
                description=strip_html(it.get("description")),
                posted_date=to_date(it.get("created")),
                posting_ref=f"AZ-{jid}" if jid else "",
                employment_hint=" ".join(x for x in [it.get("contract_time"), it.get("contract_type")] if x),
            ))
    return jobs
