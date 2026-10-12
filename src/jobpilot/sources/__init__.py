"""Job sources. Each source turns an external feed into a list of Job objects.

Free, no key:      arbeitnow, bundesagentur (Germany), ats (company watchlist:
                   Greenhouse, Lever, Ashby, Personio, Recruitee, SmartRecruiters)
Free, needs key:   adzuna (free developer key)
Paid credits:      apify (LinkedIn, Xing) with a monthly budget guard
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List

from ..config import Workspace
from ..models import Job
from .base import Http


@dataclass
class SearchContext:
    ws: Workspace
    http: Http
    today: str
    queries_en: List[str]
    queries_local: List[str]
    max_age_days: int
    run_hour: int = 0
    log: List[str] = field(default_factory=list)
    apify_spent_this_month: float = 0.0
    apify_spent_this_run: float = 0.0

    @property
    def all_queries(self) -> List[str]:
        seen, out = set(), []
        for q in self.queries_en + self.queries_local:
            if q.lower() not in seen:
                seen.add(q.lower())
                out.append(q)
        return out


def registry() -> Dict[str, Callable[[SearchContext], List[Job]]]:
    from . import adzuna, apify, arbeitnow, ats, bundesagentur
    return {
        "arbeitnow": arbeitnow.fetch,
        "bundesagentur": bundesagentur.fetch,
        "adzuna": adzuna.fetch,
        "watchlist": ats.fetch_watchlist,
        "apify_linkedin": apify.fetch_linkedin,
        "apify_xing": apify.fetch_xing,
    }
