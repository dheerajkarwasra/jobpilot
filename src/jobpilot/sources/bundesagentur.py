"""Bundesagentur fuer Arbeit (German Federal Employment Agency) Jobsuche API.

Community documented at https://jobsuche.api.bund.dev . Uses the public client key
documented there. Germany only. Marked beta: the agency may change it at any time.
"""
from __future__ import annotations

from typing import List

from ..models import Job
from .base import SourceError, to_date

URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
HEADERS = {"X-API-Key": "jobboerse-jobsuche"}
DETAIL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"


def fetch(ctx) -> List[Job]:
    if ctx.ws.get("search.country", "de") != "de":
        return []
    where = ctx.ws.get("sources.bundesagentur_where", "Deutschland")
    jobs: List[Job] = []
    errors = 0
    for q in ctx.all_queries:
        params = {"was": q, "wo": where, "veroeffentlichtseit": ctx.max_age_days, "size": 50, "page": 1}
        try:
            data = ctx.http.get_json(URL, params=params, headers=HEADERS)
        except SourceError:
            errors += 1
            if errors >= 2:
                raise
            continue
        for it in data.get("stellenangebote") or []:
            refnr = str(it.get("refnr") or "")
            ort = it.get("arbeitsort") or {}
            jobs.append(Job(
                title=str(it.get("titel") or it.get("beruf") or "").strip(),
                company=str(it.get("arbeitgeber") or "").strip(),
                link=str(it.get("externeUrl") or (DETAIL.format(refnr=refnr) if refnr else "")),
                source="Bundesagentur",
                location=", ".join(x for x in [ort.get("ort"), ort.get("region")] if x),
                description=str(it.get("beruf") or ""),
                posted_date=to_date(it.get("aktuelleVeroeffentlichungsdatum") or it.get("modifikationsTimestamp")),
                posting_ref=f"BA-{refnr}" if refnr else "",
            ))
    return jobs
