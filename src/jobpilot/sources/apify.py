"""Optional paid sources through Apify (LinkedIn, Xing).

Needs JOBPILOT_APIFY_TOKEN in .env. Every run estimates cost and the search skips
Apify once the monthly budget in profile.yaml (sources.apify_monthly_budget_usd)
would be exceeded. The Apify free plan includes about 5 USD of usage per month.
"""
from __future__ import annotations

from typing import List

from ..models import Job
from .base import SourceError, strip_html, to_date

RUN_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
LINKEDIN_ACTOR = "curious_coder~linkedin-jobs-scraper"
XING_ACTOR = "shahidirfan~Xing-Jobs-Scraper"
COST_PER_ITEM = {"linkedin": 0.002, "xing": 0.0015}


def _token(ctx) -> str:
    tok = ctx.ws.env.get("JOBPILOT_APIFY_TOKEN")
    if not tok:
        raise SourceError("Apify token missing (JOBPILOT_APIFY_TOKEN)")
    return tok


def _allowed(ctx, planned_cost: float) -> bool:
    budget = float(ctx.ws.get("sources.apify_monthly_budget_usd", 4.0))
    hours = ctx.ws.get("sources.apify_run_hours", [6, 18])
    if hours and ctx.run_hour not in hours and ctx.ws.get("sources.apify_respect_hours", True):
        ctx.log.append(f"apify skipped (runs only at hours {hours})")
        return False
    with ctx.lock:
        if ctx.apify_spent_this_month + ctx.apify_spent_this_run + planned_cost > budget:
            ctx.log.append(f"apify skipped (monthly budget {budget} USD reached)")
            return False
        # reserve the planned cost so two parallel apify sources cannot both pass the check
        ctx.apify_spent_this_run += planned_cost
    return True


def _run(ctx, actor: str, payload: dict, max_items: int, kind: str) -> list:
    cost = max_items * COST_PER_ITEM[kind]
    params = {"token": _token(ctx), "timeout": 240, "maxItems": max_items, "maxTotalChargeUsd": round(cost * 1.5, 2)}
    items = ctx.http.post_json(RUN_URL.format(actor=actor), payload, params=params, timeout=300)
    with ctx.lock:
        # replace the reservation for these items with what actually came back
        ctx.apify_spent_this_run += (len(items) - max_items) * COST_PER_ITEM[kind]
    return items


def fetch_linkedin(ctx) -> List[Job]:
    queries = ctx.ws.get("sources.apify_linkedin_queries") or ctx.queries_en[:3]
    per = int(ctx.ws.get("sources.apify_linkedin_per_query", 30))
    if not _allowed(ctx, len(queries) * per * COST_PER_ITEM["linkedin"]):
        return []
    country = ctx.ws.country.get("name", "Germany")
    out: List[Job] = []
    for q in queries:
        payload = {"keywords": q, "location": country, "datePosted": "past24Hours",
                   "limitPerSource": per, "scrapeCompany": False}
        for it in _run(ctx, LINKEDIN_ACTOR, payload, per, "linkedin"):
            jid = str(it.get("id") or "")
            link = str(it.get("link") or "")
            if not jid and "/jobs/view/" in link:
                jid = link.split("/jobs/view/")[1].split("?")[0].rsplit("-", 1)[-1]
            out.append(Job(
                title=str(it.get("title") or ""), company=str(it.get("companyName") or ""),
                link=f"https://www.linkedin.com/jobs/view/{jid}" if jid else link, source="LinkedIn",
                location=str(it.get("location") or ""), description=str(it.get("descriptionText") or ""),
                posted_date=to_date(it.get("postedAt")), posting_ref=f"LI-{jid}" if jid else "",
                employment_hint=str(it.get("employmentType") or ""),
            ))
    return out


def fetch_xing(ctx) -> List[Job]:
    queries = ctx.ws.get("sources.apify_xing_queries") or ctx.queries_local[:1] or ctx.queries_en[:1]
    per = int(ctx.ws.get("sources.apify_xing_per_query", 40))
    if not _allowed(ctx, len(queries) * per * COST_PER_ITEM["xing"]):
        return []
    out: List[Job] = []
    for q in queries:
        payload = {"keyword": q, "location": "Deutschland", "date_posted": "LAST_24_HOURS",
                   "results_wanted": per, "max_pages": 2}
        for it in _run(ctx, XING_ACTOR, payload, per, "xing"):
            jid = str(it.get("job_id") or "")
            out.append(Job(
                title=str(it.get("title") or ""), company=str(it.get("company") or ""),
                link=str(it.get("url") or ""), source="Xing", location=str(it.get("location") or ""),
                description=strip_html(it.get("description_text") or it.get("description_html")),
                posted_date=to_date(it.get("date_posted")),
                posting_ref=str(it.get("job_code") or (f"XI-{jid}" if jid else "")),
                employment_hint=str(it.get("job_type") or ""),
            ))
    return out
