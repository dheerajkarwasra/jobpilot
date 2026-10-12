"""`jobpilot search`: collect, filter, score, de-duplicate, write to the tracker."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional

from .config import Workspace
from .models import Job
from .pipeline import Pipeline
from .sources import SearchContext, registry
from .sources.base import Http
from .tracker import open_tracker


def _apify_spent_this_month(tracker, month: str) -> float:
    total = 0.0
    for row in tracker.run_log():
        if str(row.get("Run Time", "")).startswith(month):
            m = re.search(r"apify=([0-9.]+)", str(row.get("Notes", "")))
            if m:
                total += float(m.group(1))
    return total


def enabled_sources(ws: Workspace, only: Optional[List[str]] = None) -> List[str]:
    src = ws.get("sources", {}) or {}
    names = []
    if src.get("arbeitnow", True) and ws.get("search.country", "de") in ("de", "at", "ch"):
        names.append("arbeitnow")
    if src.get("bundesagentur", True) and ws.get("search.country", "de") == "de":
        names.append("bundesagentur")
    if src.get("adzuna", False):
        names.append("adzuna")
    if src.get("watchlist", True) and ws.get("watchlist"):
        names.append("watchlist")
    if src.get("apify_linkedin", False):
        names.append("apify_linkedin")
    if src.get("apify_xing", False) and ws.get("search.country", "de") in ("de", "at", "ch"):
        names.append("apify_xing")
    if only:
        names = [n for n in names if n in only] or [n for n in only if n in registry()]
    return names


def run_search(ws: Workspace, only: Optional[List[str]] = None, dry_run: bool = False,
               http: Optional[Http] = None, now: Optional[datetime] = None, quiet: bool = False) -> Dict:
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")
    tracker = open_tracker(ws)
    ctx = SearchContext(
        ws=ws, http=http or Http(), today=today,
        queries_en=list(ws.get("search.queries_en", []) or []),
        queries_local=list(ws.get("search.queries_local", []) or []),
        max_age_days=int(ws.get("search.max_age_days", 3)),
        run_hour=now.hour,
        apify_spent_this_month=_apify_spent_this_month(tracker, now.strftime("%Y-%m")),
    )
    raw: List[Job] = []
    ok, failed = [], []
    reg = registry()
    names = enabled_sources(ws, only)
    # Sources run in parallel but results are collected in a fixed order,
    # so job IDs stay deterministic. A broken source must never stop the run.
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(names)))) as pool:
        futures = [(name, pool.submit(reg[name], ctx)) for name in names]
        for name, fut in futures:
            try:
                got = fut.result()
                raw.extend(got)
                ok.append(f"{name}({len(got)})")
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{name}: {str(exc)[:120]}")

    links, refs, keys = tracker.existing_sets()
    pipe = Pipeline(ws, today=today)
    new_jobs, stats = pipe.process(raw, links, refs, keys)

    start = tracker.next_id()
    rows = [j.to_row(f"J{start + i:04d}", today) for i, j in enumerate(new_jobs)]
    apify_note = f"apify={ctx.apify_spent_this_run:.2f}" if any(n.startswith("apify") for n in enabled_sources(ws, only)) else ""
    notes = ", ".join(f"{k}={v}" for k, v in stats.items()) + (f", {apify_note}" if apify_note else "")
    if ctx.log:
        notes += " | " + " | ".join(ctx.log)
    if not dry_run:
        tracker.append_jobs(rows)
        tracker.sync_watchlist(ws.get("watchlist", []) or [], today)
        tracker.refresh_review_queue()
        tracker.log_run([now.strftime("%Y-%m-%d %H:%M"), "Job search", len(rows), 0, ", ".join(ok),
                         "; ".join(failed), notes])
        tracker.save()
    result = {"new": new_jobs, "rows": rows, "stats": stats, "ok": ok, "failed": failed, "notes": notes,
              "high": [r for r in rows if r[2] == "High"]}
    if not quiet:
        print_summary(result, dry_run)
    return result


def print_summary(result: Dict, dry_run: bool = False) -> None:
    rows = result["rows"]
    print(f"{'[dry run] ' if dry_run else ''}{len(rows)} new postings "
          f"({result['stats']['raw']} raw, {result['stats']['duplicate']} duplicates, "
          f"{result['stats']['raw'] - result['stats']['kept'] - result['stats']['duplicate']} filtered out)")
    dropped = {k: v for k, v in result["stats"].items() if k not in ("raw", "kept", "duplicate") and v}
    if dropped:
        print("Dropped by filter: " + ", ".join(f"{k} {v}" for k, v in sorted(dropped.items(), key=lambda x: -x[1])))
    if result["ok"]:
        print("Sources ok: " + ", ".join(result["ok"]))
    if result["failed"]:
        print("Sources failed: " + "; ".join(result["failed"]))
    high = result["high"]
    if high:
        print(f"\nHigh fit ({len(high)}):")
        for r in high[:25]:
            print(f"  {r[0]}  {r[4]}  |  {r[5]}  |  {r[8]}  |  lang req: {r[11]}  |  {r[15]}")
