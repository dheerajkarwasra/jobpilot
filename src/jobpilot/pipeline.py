"""Filtering, language detection, scoring and de-duplication.

Everything here is deterministic and driven by profile.yaml, so results are the
same no matter which AI assistant the user works with.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .config import Workspace
from .models import Job

CEFR = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6, "native": 7, "fluent": 5}

_GENDER = re.compile(r"\((?:[mwfdxa]\s*/\s*){1,3}[mwfdxa]\)|\b(?:[mwfdx]\s*/\s*){2}[mwfdx]\b|all genders|alle geschlechter|"
                     r"\(all\)|\bm\|w\|d\b|\(gn\)|\(w/m/x\)", re.I)
_LEGAL = re.compile(r"\b(gmbh|ag|se|kg|kgaa|ohg|ug|e\.?v\.?|inc|ltd|llc|plc|co|corp|holding|group|& co)\b\.?", re.I)


def _kw_regex(word: str) -> re.Pattern:
    w = re.escape(word.lower().strip())
    if len(word.strip()) <= 3:
        return re.compile(rf"(?<![a-z0-9äöü]){w}(?![a-z0-9äöü])")
    return re.compile(w)


def has_any(text: str, words: Iterable[str]) -> List[str]:
    t = text.lower()
    return [w for w in words if w and _kw_regex(w).search(t)]


def norm_company(name: str) -> str:
    s = _LEGAL.sub(" ", name.lower())
    return re.sub(r"[^a-z0-9äöüß]+", "", s)


def norm_title(title: str) -> str:
    s = _GENDER.sub(" ", title.lower())
    return re.sub(r"[^a-z0-9äöüß]+", "", s)


def dedupe_key(job: Job) -> str:
    return f"{norm_company(job.company)}|{norm_title(job.title)}"


def canonical_link(link: str) -> str:
    l = link.strip()
    if "linkedin.com/jobs/view/" in l:
        tail = l.split("/jobs/view/")[1].split("?")[0].strip("/")
        return "linkedin:" + tail.rsplit("-", 1)[-1]
    return l.split("?")[0].rstrip("/").lower() if "indeed" not in l else l.lower()


# ---------------------------------------------------------------------------
class Pipeline:
    def __init__(self, ws: Workspace, today: Optional[str] = None):
        self.ws = ws
        self.d = ws.defaults
        self.today = today or date.today().isoformat()
        self.role_types: List[str] = ws.get("search.role_types", ["werkstudent", "internship", "entry"])
        self.must_match: List[str] = [w.lower() for w in ws.get("search.must_match_any", [])]
        self.exclude_title: List[str] = [w.lower() for w in ws.get("search.exclude_title", [])]
        self.exclude_desc: List[str] = [w.lower() for w in ws.get("search.exclude_description", [])]
        self.exclude_companies: List[str] = [norm_company(c) for c in ws.get("search.exclude_companies", [])]
        self.max_age = int(ws.get("search.max_age_days", 3))
        self.country = ws.country
        self.loc_keywords: List[str] = [w.lower() for w in (ws.get("search.location_keywords")
                                                             or self.country.get("location_keywords", []))]
        self.allow_remote: bool = bool(ws.get("search.remote_ok", True))
        self.local_lang: Optional[str] = ws.get("search.local_language", self.country.get("language"))
        self.lang_rules: Dict = (self.d["languages"].get(self.local_lang) or {}) if self.local_lang else {}
        self.user_local_level = self._user_level(self.local_lang)
        self.ok_level = CEFR.get(str(ws.get("search.max_local_language_level_ok", "A2")).lower(), 2)
        sc = dict(self.d["scoring"])
        sc.update(ws.get("scoring.weights", {}) or {})
        self.sc = sc
        kws = ws.get("scoring.keywords", {}) or {}
        self.kw_primary = [w.lower() for w in kws.get("primary", [])]
        self.kw_core = [w.lower() for w in kws.get("core", [])]
        self.kw_secondary = [w.lower() for w in kws.get("secondary", [])]
        self.penalize_fulltime = bool(ws.get("scoring.penalize_fulltime", True))
        self.watch_names = {norm_company(w.get("name", "")) for w in (ws.get("watchlist", []) or [])}
        self.consultancy = [w.lower() for w in sc.get("consultancy_markers", [])]

    # -- helpers ---------------------------------------------------------------
    def _user_level(self, lang: Optional[str]) -> int:
        if not lang:
            return 7
        for l in self.ws.get("languages", []) or []:
            if str(l.get("language", "")).lower() == lang.lower():
                return CEFR.get(str(l.get("level", "a1")).lower(), 1)
        return 0

    def classify_type(self, job: Job) -> Optional[str]:
        t = f" {job.title.lower()} "
        order = ["thesis", "werkstudent", "internship", "entry"]
        for rt in order:
            markers = self.d["role_types"][rt]["title_markers"]
            if has_any(t, markers):
                return self.d["role_types"][rt]["type_label"] if rt in self.role_types else None
        hint = job.employment_hint.lower()
        if "intern" in hint and "internship" in self.role_types:
            return "Internship"
        if ("student" in hint or "werkstudent" in hint) and "werkstudent" in self.role_types:
            return "Werkstudent"
        if "fulltime" in self.role_types:
            if re.search(r"\b(senior|staff|principal|lead|head of|director|manager|leiter)\b", job.title.lower()):
                return None if not self.ws.get("search.include_senior", False) else "Full time"
            return "Full time"
        return None

    def in_location(self, job: Job) -> bool:
        loc = f"{job.location} {job.title}".lower()
        if job.source in ("Arbeitnow", "Bundesagentur") and self.ws.get("search.country", "de") == "de" and not job.location:
            return True
        if not self.loc_keywords:
            return True
        if has_any(loc, self.loc_keywords):
            return True
        if self.allow_remote and (job.remote_hint or has_any(loc, self.d["remote_keywords"])):
            # remote roles must not be tied to another country only
            return not re.search(r"\b(us only|usa only|united states only|uk only|canada only)\b", loc)
        return False

    def too_old(self, job: Job) -> bool:
        if not job.posted_date:
            return False
        try:
            posted = datetime.strptime(job.posted_date[:10], "%Y-%m-%d").date()
        except ValueError:
            return False
        return posted < date.fromisoformat(self.today) - timedelta(days=self.max_age)

    def posting_language(self, job: Job) -> str:
        text = f" {job.title} {job.description[:3000]} ".lower()
        words = re.findall(r"[a-zäöüßéèàç]+", text)
        if not words:
            return ""
        en = sum(1 for w in words if w in set(self.d["english_stopwords"]))
        loc = 0
        code = ""
        if self.lang_rules:
            sw = set(self.lang_rules.get("stopwords", []))
            loc = sum(1 for w in words if w in sw)
            code = self.lang_rules.get("code", "").upper()
        if not code:
            return "EN"
        if en and loc and min(en, loc) / max(en, loc) > 0.6:
            return f"EN/{code}"
        return "EN" if en >= loc else code

    def language_required(self, job: Job, plang: str) -> str:
        if not self.lang_rules or self.user_local_level >= 4:   # user has B2+ in local language
            return "No"
        text = f"{job.title} {job.description}".lower()
        if has_any(text, self.lang_rules.get("required", [])):
            return "Required" if self.ok_level < 4 else "Optional"
        if has_any(text, self.lang_rules.get("optional", [])) or has_any(text, self.lang_rules.get("english_ok", [])):
            return "Optional"
        if not job.description.strip():
            return "Unknown" if plang in ("EN", "") else "Likely"
        if plang == "EN":
            return "No"
        return "Likely"

    def work_mode(self, job: Job) -> str:
        if job.remote_hint is True:
            return "Remote"
        text = f"{job.location} {job.title} {job.description[:4000]}".lower()
        if has_any(text, ["hybrid", "home office möglich", "homeoffice möglich", "teilweise remote", "mobiles arbeiten",
                          "mobile work", "partly remote", "flexible working"]):
            return "Hybrid"
        if has_any(f"{job.location} {job.title}".lower(), ["remote", "100% remote", "fully remote"]):
            return "Remote"
        if has_any(text, ["on-site", "onsite", "vor ort", "in-office"]):
            return "Onsite"
        return "Unknown"

    def score(self, job: Job) -> Tuple[int, str, List[str]]:
        text = f"{job.title} {job.description}".lower()
        s, why = 0, []
        if job.posting_language.startswith("EN") or job.language_required in ("No", "Optional"):
            s += self.sc["english_or_language_ok"]; why.append("language ok")
        p = has_any(text, self.kw_primary)
        if p:
            s += self.sc["primary_keyword"]; why.append("+" + "/".join(p[:3]))
        c = has_any(text, self.kw_core)
        if c:
            s += self.sc["core_keyword"]; why.append("+" + "/".join(c[:3]))
        sec = has_any(text, self.kw_secondary)
        if sec:
            s += self.sc["secondary_keyword"]; why.append("+" + "/".join(sec[:2]))
        if norm_company(job.company) in self.watch_names:
            s += self.sc["watchlist_company"]; why.append("watchlist")
        if job.language_required == "Likely":
            s += self.sc["language_likely_needed"]; why.append(f"{self.local_lang or 'local language'} likely needed")
        if self.penalize_fulltime and job.type in ("Entry", "Full time") and \
                has_any(f"{job.employment_hint} {job.title}".lower(), ["full-time", "full time", "fulltime", "vollzeit", "permanent"]):
            s += self.sc["fulltime_visa_risk"]; why.append("full time (check permit)")
        if has_any(job.company.lower(), self.consultancy):
            s += self.sc["consultancy"]; why.append("consultancy")
        fit = "High" if s >= self.sc["high_threshold"] else "Medium" if s >= self.sc["medium_threshold"] else "Low"
        return s, fit, why

    # -- main ------------------------------------------------------------------
    def process(self, jobs: List[Job], existing_links: Set[str], existing_refs: Set[str],
                existing_keys: Set[str]) -> Tuple[List[Job], Dict[str, int]]:
        stats = {"raw": len(jobs), "old": 0, "type": 0, "location": 0, "excluded": 0, "irrelevant": 0,
                 "language": 0, "duplicate": 0, "kept": 0}
        kept: Dict[str, Job] = {}
        seen_links: Set[str] = set()
        for job in jobs:
            if not job.title or not job.link:
                stats["irrelevant"] += 1; continue
            if self.too_old(job):
                stats["old"] += 1; continue
            jtype = self.classify_type(job)
            if not jtype:
                stats["type"] += 1; continue
            job.type = jtype
            if not self.in_location(job):
                stats["location"] += 1; continue
            title_l = job.title.lower()
            if has_any(f" {title_l} ", self.exclude_title) or norm_company(job.company) in self.exclude_companies \
                    or any(norm_company(job.company).startswith(x) for x in self.exclude_companies if len(x) > 4) \
                    or has_any(job.description.lower(), self.exclude_desc):
                stats["excluded"] += 1; continue
            if self.must_match and not has_any(f"{job.title} {job.description}".lower(), self.must_match):
                stats["irrelevant"] += 1; continue
            job.posting_language = self.posting_language(job)
            job.language_required = self.language_required(job, job.posting_language)
            if job.language_required == "Required":
                stats["language"] += 1; continue
            job.work_mode = self.work_mode(job)
            if not job.posting_ref:
                job.posting_ref = "WEB-" + re.sub(r"[^a-z0-9]+", "-", norm_title(job.title))[:20]
            clink = canonical_link(job.link)
            key = dedupe_key(job)
            if clink in existing_links or job.posting_ref in existing_refs or key in existing_keys or clink in seen_links:
                stats["duplicate"] += 1; continue
            job.score, job.fit, job.reasons = self.score(job)
            prev_note = job.notes
            job.notes = "; ".join(job.reasons)
            if key in kept:
                stats["duplicate"] += 1
                other = kept[key]
                better, worse = (job, other) if len(job.description) > len(other.description) else (other, job)
                better.notes = (better.notes + f"; also on {worse.source} {worse.posting_ref}").strip("; ")
                kept[key] = better
                continue
            if prev_note == "watchlist" and "watchlist" not in job.notes:
                job.notes = (job.notes + "; watchlist").strip("; ")
            kept[key] = job
            seen_links.add(clink)
        out = sorted(kept.values(), key=lambda j: (-j.score, j.company.lower()))
        stats["kept"] = len(out)
        return out, stats
