"""Backend independent tracker logic."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from ..config import Workspace
from ..models import (APPLICATION_COLUMNS, JOB_COLUMNS, RUNLOG_COLUMNS, STATUS_RANK, STATUSES,
                      WATCHLIST_COLUMNS)
from ..pipeline import canonical_link, norm_company, norm_title

FIT_RANK = {"High": 0, "Medium": 1, "Low": 2}
DASH_START_ROW = 4
SHEETS = ["Dashboard", "Review Queue", "Jobs", "Applications", "Watchlist", "Run Log"]


def _int(v: Any) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def col_letter(idx: int) -> str:
    s = ""
    idx += 1
    while idx:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def jcol(name: str) -> str:
    return col_letter(JOB_COLUMNS.index(name))


def acol(name: str) -> str:
    return col_letter(APPLICATION_COLUMNS.index(name))


def dashboard_cells() -> List[Tuple[str, Any]]:
    """(label, formula) pairs used by both backends."""
    st, fit, lang, found, src = jcol("Status"), jcol("Fit"), jcol("Posting Language"), jcol("Date Found"), jcol("Source")
    ids = jcol("ID")
    r = lambda c: f"Jobs!{c}2:{c}5000"  # noqa: E731
    rows: List[Tuple[str, Any]] = [
        ("PIPELINE", None),
        ("Total postings tracked", f"=COUNTA({r(ids)})"),
        ("To review (Found)", f'=COUNTIF({r(st)},"Found")'),
        ("High fit to review", f'=COUNTIFS({r(st)},"Found",{r(fit)},"High")'),
        ("Found in last 7 days", f'=SUMPRODUCT(--({r(found)}>=TEXT(TODAY()-7,"yyyy-mm-dd")))'),
        ("Shortlisted", f'=COUNTIF({r(st)},"Shortlisted")'),
        ("English postings", f'=COUNTIF({r(lang)},"EN*")'),
        ("", None),
        ("APPLICATIONS", None),
    ]
    pos = {}
    for s in ["Applied", "Screening", "Interview", "Offer", "Rejected", "Ghosted"]:
        pos[s] = DASH_START_ROW + len(rows)
        rows.append((s, f'=COUNTIF({r(st)},"{s}")'))
    rows += [("", None), ("RATES", None)]
    sent_row = DASH_START_ROW + len(rows)
    b = lambda s: f"B{pos[s]}"  # noqa: E731
    rows += [("Applications sent", f"=SUM(B{pos['Applied']}:B{pos['Ghosted']})"),
             ("Interview rate", f"=IF(B{sent_row}=0,0,({b('Interview')}+{b('Offer')})/B{sent_row})"),
             ("Response rate", f"=IF(B{sent_row}=0,0,({b('Screening')}+{b('Interview')}+{b('Offer')}+{b('Rejected')})/B{sent_row})"),
             ("", None), ("SOURCES", None)]
    for s in ["Arbeitnow", "Bundesagentur", "Adzuna", "LinkedIn", "Xing"]:
        rows.append((s, f'=COUNTIF({r(src)},"{s}")'))
    rows.append(("Company sites (watchlist)", f'=COUNTIF({r(src)},"Company site*")'))
    rows.append(("Added manually", f'=COUNTIF({r(src)},"Manual")'))
    return rows


HOW_TO = [
    "HOW TO USE",
    "1. Review Queue lists every posting with Status = Found, best fit first. It is rebuilt on each search run.",
    "2. In Jobs, set Status to Shortlisted, Skipped or Applied. Or tell your AI assistant: 'mark J0012 applied'.",
    "3. Ask your assistant to prepare an application: '/jobpilot-apply J0012' (Claude Code) or '$jobpilot-apply J0012' (Codex).",
    "4. The inbox check (if enabled) moves Applied rows to Screening, Interview, Offer or Rejected from email replies.",
    "5. Fit comes from a points rubric in profile.yaml (scoring). Language Required is detected from the description, verify it.",
    "6. Edit search terms, exclusions and the watchlist in profile.yaml or with `jobpilot watchlist add`.",
]


class Tracker:
    """Shared logic. Backends implement the _abstract_ methods."""

    def __init__(self, ws: Workspace):
        self.ws = ws

    # --- abstract -------------------------------------------------------------
    def _rows(self, sheet: str) -> List[List[Any]]:
        raise NotImplementedError

    def _append(self, sheet: str, rows: List[List[Any]]) -> None:
        raise NotImplementedError

    def _update_cells(self, sheet: str, updates: List[Tuple[int, int, Any]]) -> None:
        """updates: (row_index starting at 1 incl. header, col_index starting at 0, value)"""
        raise NotImplementedError

    def _replace_sheet(self, sheet: str, header: List[str], rows: List[List[Any]]) -> None:
        raise NotImplementedError

    def save(self) -> None:
        pass

    # --- reading --------------------------------------------------------------
    def table(self, sheet: str, columns: List[str]) -> List[Dict[str, Any]]:
        rows = self._rows(sheet)
        if not rows:
            return []
        header = [str(h or "") for h in rows[0]]
        out = []
        for i, r in enumerate(rows[1:], start=2):
            if not any(v not in (None, "") for v in r):
                continue
            d = {h: (r[j] if j < len(r) else "") for j, h in enumerate(header)}
            for c in columns:
                d.setdefault(c, "")
            d["_row"] = i
            out.append(d)
        return out

    def jobs(self) -> List[Dict[str, Any]]:
        return self.table("Jobs", JOB_COLUMNS)

    def applications(self) -> List[Dict[str, Any]]:
        return self.table("Applications", APPLICATION_COLUMNS)

    def find_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        job_id = job_id.strip().upper()
        for j in self.jobs():
            if str(j["ID"]).upper() == job_id:
                return j
        return None

    def existing_sets(self) -> Tuple[Set[str], Set[str], Set[str]]:
        links, refs, keys = set(), set(), set()
        for j in self.jobs():
            if j["Link"]:
                links.add(canonical_link(str(j["Link"])))
            if j["Posting Ref"]:
                refs.add(str(j["Posting Ref"]))
            keys.add(f"{norm_company(str(j['Company']))}|{norm_title(str(j['Title']))}")
        return links, refs, keys

    def next_id(self) -> int:
        n = 0
        for j in self.jobs():
            s = str(j["ID"]).upper().lstrip("J")
            if s.isdigit():
                n = max(n, int(s))
        return n + 1

    # --- writing --------------------------------------------------------------
    def append_jobs(self, rows: List[List[Any]]) -> None:
        if rows:
            self._append("Jobs", rows)

    def update_job(self, job_id: str, changes: Dict[str, Any], today: str, force: bool = False) -> Dict[str, Any]:
        job = self.find_job(job_id)
        if not job:
            raise KeyError(f"No job with ID {job_id}")
        if "Status" in changes:
            new = changes["Status"]
            if new not in STATUSES:
                raise ValueError(f"Unknown status {new}. Use one of: {', '.join(STATUSES)}")
            if not force and STATUS_RANK.get(new, 0) < STATUS_RANK.get(str(job["Status"]), 0):
                changes = {k: v for k, v in changes.items() if k != "Status"}
        changes = dict(changes)
        changes["Last Update"] = today
        if changes.get("Status") == "Applied" and not job.get("Applied Date"):
            changes.setdefault("Applied Date", today)
        upd = [(job["_row"], JOB_COLUMNS.index(k), v) for k, v in changes.items() if k in JOB_COLUMNS]
        self._update_cells("Jobs", upd)
        job.update(changes)
        return job

    def prepend_job_note(self, job_id: str, note: str, today: str) -> None:
        job = self.find_job(job_id)
        if job:
            old = str(job.get("Notes") or "")
            self._update_cells("Jobs", [(job["_row"], JOB_COLUMNS.index("Notes"), f"{today}: {note}. {old}".strip())])

    def find_application(self, job_id: str) -> Optional[Dict[str, Any]]:
        for a in self.applications():
            if str(a["Job ID"]).upper() == job_id.upper():
                return a
        return None

    def upsert_application(self, job_id: str, values: Dict[str, Any]) -> None:
        app = self.find_application(job_id)
        if app:
            upd = [(app["_row"], APPLICATION_COLUMNS.index(k), v) for k, v in values.items() if k in APPLICATION_COLUMNS]
            self._update_cells("Applications", upd)
        else:
            job = self.find_job(job_id) or {}
            base = {"Job ID": job_id, "Company": job.get("Company", ""), "Title": job.get("Title", ""),
                    "Posting Ref": job.get("Posting Ref", ""), "Status": "Applied"}
            base.update(values)
            self._append("Applications", [[base.get(c, "") for c in APPLICATION_COLUMNS]])

    def log_run(self, row: List[Any]) -> None:
        self._append("Run Log", [row])

    def run_log(self) -> List[Dict[str, Any]]:
        return self.table("Run Log", RUNLOG_COLUMNS)

    def sync_watchlist(self, entries: List[Dict[str, Any]], today: str) -> None:
        rows = [[e.get("name", ""), "Yes" if e.get("active", True) else "No", e.get("ats", ""), e.get("slug", ""),
                 e.get("why", ""), today if e.get("ats") else "not found"] for e in entries]
        self._replace_sheet("Watchlist", WATCHLIST_COLUMNS, rows)

    def refresh_review_queue(self) -> None:
        found = [j for j in self.jobs() if str(j["Status"]) == "Found"]
        # Stable sorts: newest first, then by score, then fit band on top.
        found.sort(key=lambda j: str(j["Posted Date"] or ""), reverse=True)
        found.sort(key=lambda j: _int(j["Score"]), reverse=True)
        found.sort(key=lambda j: FIT_RANK.get(str(j["Fit"]), 3))
        cols = ["ID", "Fit", "Score", "Company", "Title", "Posting Ref", "Type", "Location", "Language Required",
                "Posted Date", "Link"]
        self._replace_sheet("Review Queue", cols, [[j.get(c, "") for c in cols] for j in found])
