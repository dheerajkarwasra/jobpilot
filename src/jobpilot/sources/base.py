"""Shared helpers for job sources."""
from __future__ import annotations

import html
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from .. import __version__

USER_AGENT = f"JobPilot/{__version__} (+https://github.com/jobpilot; personal job search tool)"
TIMEOUT = 30


class SourceError(RuntimeError):
    pass


RETRY_STATUS = (429, 500, 502, 503, 504)


class Http:
    """Tiny wrapper so tests can swap the network layer.

    Transient failures (timeouts, connection errors, 429 and 5xx) are retried
    with a short backoff so one network hiccup does not fail a whole source.
    """

    def __init__(self, session: Optional[requests.Session] = None, delay: float = 0.5, retries: int = 2):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.delay = delay
        self.retries = retries

    def _request(self, method: str, url: str, timeout: int = TIMEOUT, **kwargs: Any) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            if attempt:
                time.sleep(min(2 ** attempt, 8))
            try:
                resp = self.session.request(method, url, timeout=timeout, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                continue
            if resp.status_code in RETRY_STATUS and attempt < self.retries:
                ra = resp.headers.get("Retry-After", "")
                if ra.isdigit() and int(ra) <= 30:
                    time.sleep(int(ra))
                continue
            return resp
        raise SourceError(f"request failed after {self.retries + 1} attempts: {url} ({last_exc})") from last_exc

    def get(self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> requests.Response:
        resp = self._request("GET", url, params=params, headers=headers)
        if self.delay:
            time.sleep(self.delay)
        return resp

    def get_json(self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> Any:
        resp = self.get(url, params=params, headers=headers)
        if resp.status_code == 404:
            raise SourceError(f"404 Not Found: {url}")
        if resp.status_code >= 400:
            raise SourceError(f"HTTP {resp.status_code} from {url}: {resp.text[:200]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise SourceError(f"Invalid JSON from {url}") from exc

    def get_text(self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> str:
        resp = self.get(url, params=params, headers=headers)
        if resp.status_code >= 400:
            raise SourceError(f"HTTP {resp.status_code} from {url}")
        return resp.text

    def post_json(self, url: str, payload: Any, params: Optional[dict] = None, timeout: int = 300) -> Any:
        resp = self._request("POST", url, json=payload, params=params, timeout=timeout)
        if resp.status_code >= 400:
            raise SourceError(f"HTTP {resp.status_code} from {url}: {resp.text[:300]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise SourceError(f"Invalid JSON from {url}") from exc


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_html(text: Optional[str]) -> str:
    if not text:
        return ""
    text = html.unescape(text)          # Greenhouse double-escapes HTML
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    lines = [_WS.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def to_date(value: Any) -> str:
    """Normalise unix seconds, unix ms, ISO strings or dates to YYYY-MM-DD."""
    if value in (None, ""):
        return ""
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            v = float(value)
            if v > 1e12:  # milliseconds
                v /= 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d")
        s = str(value).strip()
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s[:25]).strftime("%Y-%m-%d") if "T" in s else s[:10]
    except (ValueError, OSError, OverflowError):
        return str(value)[:10]


def first(*values: Any) -> str:
    for v in values:
        if v:
            return str(v)
    return ""


def clean_list(items: Optional[List[Any]]) -> List[str]:
    return [str(i).strip() for i in (items or []) if str(i).strip()]


def summarize(meta: Dict[str, Any]) -> str:
    return ", ".join(f"{k}={v}" for k, v in meta.items())
