"""Company watchlist via public applicant-tracking-system (ATS) job board APIs.

These endpoints are public and meant for embedding job lists on career sites:
    greenhouse       https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
    lever            https://api.lever.co/v0/postings/{slug}?mode=json  (EU: api.eu.lever.co)
    ashby            https://api.ashbyhq.com/posting-api/job-board/{slug}
    personio         https://{slug}.jobs.personio.de/xml   (very common with German startups)
    recruitee        https://{slug}.recruitee.com/api/offers/
    smartrecruiters  https://api.smartrecruiters.com/v1/companies/{slug}/postings
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Callable, Dict, List, Optional, Tuple

from ..models import Job
from .base import Http, SourceError, strip_html, to_date


def _greenhouse(http: Http, slug: str, company: str) -> List[Job]:
    data = http.get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
    out = []
    for it in data.get("jobs") or []:
        out.append(Job(
            title=str(it.get("title") or ""), company=company, link=str(it.get("absolute_url") or ""),
            source=f"Company site (Greenhouse)", location=str((it.get("location") or {}).get("name") or ""),
            description=strip_html(it.get("content")),
            posted_date=to_date(it.get("first_published") or it.get("updated_at")),
            posting_ref=str(it.get("requisition_id") or f"GH-{it.get('id')}"),
        ))
    return out


def _lever(http: Http, slug: str, company: str) -> List[Job]:
    data = None
    for host in ("api.lever.co", "api.eu.lever.co"):
        try:
            data = http.get_json(f"https://{host}/v0/postings/{slug}", params={"mode": "json"})
            if data:
                break
        except SourceError:
            continue
    if data is None:
        raise SourceError(f"Lever board not found: {slug}")
    out = []
    for it in data or []:
        cats = it.get("categories") or {}
        out.append(Job(
            title=str(it.get("text") or ""), company=company, link=str(it.get("hostedUrl") or ""),
            source="Company site (Lever)", location=str(cats.get("location") or ""),
            description=str(it.get("descriptionPlain") or strip_html(it.get("description"))),
            posted_date=to_date(it.get("createdAt")), posting_ref=f"LV-{str(it.get('id'))[:8]}",
            employment_hint=str(cats.get("commitment") or ""),
            remote_hint=(str(it.get("workplaceType") or "").lower() == "remote") or None,
        ))
    return out


def _ashby(http: Http, slug: str, company: str) -> List[Job]:
    data = http.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    out = []
    for it in data.get("jobs") or []:
        if it.get("isListed") is False:
            continue
        out.append(Job(
            title=str(it.get("title") or ""), company=company, link=str(it.get("jobUrl") or ""),
            source="Company site (Ashby)", location=str(it.get("location") or ""),
            description=str(it.get("descriptionPlain") or strip_html(it.get("descriptionHtml"))),
            posted_date=to_date(it.get("publishedAt")), posting_ref=f"AB-{str(it.get('id'))[:8]}",
            employment_hint=str(it.get("employmentType") or ""), remote_hint=it.get("isRemote"),
        ))
    return out


def _personio(http: Http, slug: str, company: str) -> List[Job]:
    text = http.get_text(f"https://{slug}.jobs.personio.de/xml", params={"language": "en"})
    if "<workzag-jobs" not in text and "<position" not in text:
        raise SourceError(f"Personio feed not found: {slug}")
    root = ET.fromstring(text.encode("utf-8"))
    out = []
    for pos in root.iter("position"):
        pid = (pos.findtext("id") or "").strip()
        desc = " ".join(strip_html(v.findtext("value")) for v in pos.iter("jobDescription"))
        out.append(Job(
            title=(pos.findtext("name") or "").strip(), company=company,
            link=f"https://{slug}.jobs.personio.de/job/{pid}" if pid else f"https://{slug}.jobs.personio.de/",
            source="Company site (Personio)", location=(pos.findtext("office") or "").strip(),
            description=desc, posted_date=to_date(pos.findtext("createdAt")),
            posting_ref=f"PE-{pid}" if pid else "",
            employment_hint=" ".join(x for x in [pos.findtext("employmentType"), pos.findtext("schedule")] if x),
        ))
    return out


def _recruitee(http: Http, slug: str, company: str) -> List[Job]:
    data = http.get_json(f"https://{slug}.recruitee.com/api/offers/")
    out = []
    for it in data.get("offers") or []:
        out.append(Job(
            title=str(it.get("title") or ""), company=company, link=str(it.get("careers_url") or ""),
            source="Company site (Recruitee)",
            location=", ".join(x for x in [it.get("city"), it.get("country")] if x) or str(it.get("location") or ""),
            description=strip_html(it.get("description")) + "\n" + strip_html(it.get("requirements")),
            posted_date=to_date(it.get("published_at") or it.get("created_at")),
            posting_ref=f"RC-{it.get('id')}", employment_hint=str(it.get("employment_type_code") or ""),
            remote_hint=it.get("remote"),
        ))
    return out


def _smartrecruiters(http: Http, slug: str, company: str) -> List[Job]:
    data = http.get_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", params={"limit": 100})
    out = []
    for it in data.get("content") or []:
        loc = it.get("location") or {}
        pid = it.get("id")
        out.append(Job(
            title=str(it.get("name") or ""), company=company,
            link=f"https://jobs.smartrecruiters.com/{slug}/{pid}",
            source="Company site (SmartRecruiters)",
            location=", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
            description=str((it.get("function") or {}).get("label") or ""),
            posted_date=to_date(it.get("releasedDate")), posting_ref=str(it.get("refNumber") or f"SR-{pid}"),
            employment_hint=str((it.get("typeOfEmployment") or {}).get("label") or ""),
            remote_hint=loc.get("remote"),
        ))
    return out


ATS: Dict[str, Callable[[Http, str, str], List[Job]]] = {
    "greenhouse": _greenhouse,
    "lever": _lever,
    "ashby": _ashby,
    "personio": _personio,
    "recruitee": _recruitee,
    "smartrecruiters": _smartrecruiters,
}


def slug_candidates(name: str) -> List[str]:
    base = name.lower()
    base = re.sub(r"\b(gmbh|ag|se|kg|inc|ltd|llc|group|co)\b", "", base)
    words = re.findall(r"[a-z0-9]+", base.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))
    cands = ["".join(words), "-".join(words)]
    if words:
        cands.append(words[0])
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def probe(http: Http, name: str) -> Optional[Tuple[str, str, int]]:
    """Find which ATS a company uses. Returns (ats, slug, open_jobs) or None."""
    for slug in slug_candidates(name):
        for ats, fn in ATS.items():
            try:
                jobs = fn(http, slug, name)
            except Exception:  # noqa: BLE001 - any failure means "not this one"
                continue
            if jobs:
                return ats, slug, len(jobs)
    return None


def fetch_watchlist(ctx) -> List[Job]:
    out: List[Job] = []
    failed = []
    for entry in ctx.ws.get("watchlist", []) or []:
        if not entry.get("active", True) or not entry.get("ats") or not entry.get("slug"):
            continue
        fn = ATS.get(str(entry["ats"]).lower())
        if not fn:
            failed.append(f"{entry.get('name')}: unknown ATS {entry['ats']}")
            continue
        try:
            jobs = fn(ctx.http, entry["slug"], entry.get("name") or entry["slug"])
            for j in jobs:
                j.notes = "watchlist"
            out.extend(jobs)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{entry.get('name')}: {exc}")
    if failed:
        ctx.log.append("watchlist issues: " + "; ".join(failed[:5]))
    return out
