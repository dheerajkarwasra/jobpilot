"""Command line interface."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from . import __version__
from .config import ConfigError, open_workspace
from .models import STATUSES


def _ws(args):
    return open_workspace(args.workspace)


def cmd_setup(args) -> int:
    from .wizard import run
    run(args.workspace, args.answers, skip_search=args.no_search)
    return 0


def cmd_search(args) -> int:
    from .search import run_search
    res = run_search(_ws(args), only=args.sources, dry_run=args.dry_run, quiet=args.quiet)
    if args.quiet:
        print(f"{date.today()} search: {len(res['rows'])} new, failed: {'; '.join(res['failed']) or 'none'}")
    return 0


def cmd_inbox(args) -> int:
    from .inbox import run_inbox
    ws = _ws(args)
    if not ws.get("inbox.enabled", False) and not args.force:
        print("Inbox check is off. Run `jobpilot setup` to enable it, or pass --force.")
        return 1
    res = run_inbox(ws, days=args.days, quiet=args.quiet)
    if args.quiet:
        print(f"{date.today()} inbox: {len(res['changes'])} updates, {len(res['follow_ups'])} follow-ups due")
    return 0


def cmd_status(args) -> int:
    from .tracker import open_tracker
    ws = _ws(args)
    t = open_tracker(ws)
    jobs = t.jobs()
    counts = {s: 0 for s in STATUSES}
    for j in jobs:
        counts[str(j["Status"])] = counts.get(str(j["Status"]), 0) + 1
    print(f"Tracked: {len(jobs)}   " + "   ".join(f"{k}: {v}" for k, v in counts.items() if v))
    apps = [a for a in t.applications() if str(a["Status"]) in ("Screening", "Interview", "Offer")]
    if apps:
        print("\nActive processes:")
        for a in apps:
            print(f"  {a['Job ID']}  {a['Company']}  {a['Status']}  next: {a['Next Step']}  {a['Interview Date']}")
    due = [a for a in t.applications() if str(a["Next Step"]).startswith("Send polite follow-up")]
    if due:
        print("\nFollow-ups due:")
        for a in due:
            print(f"  {a['Job ID']}  {a['Company']}  applied {a['Applied Date']}")
    queue = [j for j in jobs if str(j["Status"]) == "Found"]
    rank = {"High": 0, "Medium": 1, "Low": 2}
    queue.sort(key=lambda j: str(j["Posted Date"] or ""), reverse=True)
    queue.sort(key=lambda j: rank.get(str(j["Fit"]), 3))
    if queue:
        print(f"\nReview queue (top {min(args.limit, len(queue))} of {len(queue)}):")
        for j in queue[:args.limit]:
            print(f"  {j['ID']}  {j['Fit']:<6} {str(j['Company'])[:28]:<28} {str(j['Title'])[:60]:<60} "
                  f"lang:{j['Language Required']}  {j['Link']}")
    runs = t.run_log()[-3:]
    if runs:
        print("\nLast runs:")
        for r in runs:
            print(f"  {r['Run Time']}  {r['Task']}  new {r['New Postings']}  updated {r['Updated Records']}  "
                  f"failed: {r['Sources Failed'] or 'none'}")
    return 0


def cmd_show(args) -> int:
    from .tracker import open_tracker
    t = open_tracker(_ws(args))
    j = t.find_job(args.id)
    if not j:
        print(f"No job {args.id}")
        return 1
    for k, v in j.items():
        if not k.startswith("_") and v not in ("", None):
            print(f"{k}: {v}")
    a = t.find_application(args.id)
    if a:
        print("\nApplication:")
        for k, v in a.items():
            if not k.startswith("_") and v not in ("", None):
                print(f"  {k}: {v}")
    return 0


def cmd_track(args) -> int:
    from .tracker import open_tracker
    status = next((s for s in STATUSES if s.lower() == args.status.lower()), None)
    if not status:
        print(f"Unknown status. Use one of: {', '.join(STATUSES)}")
        return 1
    ws = _ws(args)
    t = open_tracker(ws)
    today = date.today().isoformat()
    job = t.update_job(args.id, {"Status": status}, today, force=args.force)
    if args.note:
        t.prepend_job_note(args.id, args.note, today)
    if status in ("Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn", "Ghosted"):
        values = {"Status": status}
        if status == "Applied":
            from datetime import timedelta
            values.update({"Applied Date": today, "Next Step": "Wait",
                           "Follow-up Due": (date.today() + timedelta(days=14)).isoformat()})
            if args.note:
                values["Documents Sent"] = args.note
        else:
            values["Last Response Date"] = today
        if args.interview:
            values["Interview Date"] = args.interview
        t.upsert_application(args.id, values)
    t.refresh_review_queue()
    t.save()
    print(f"{args.id} {job['Company']}: {job['Status']}")
    return 0


def cmd_add(args) -> int:
    from .models import Job
    from .pipeline import Pipeline
    from .tracker import open_tracker
    ws = _ws(args)
    t = open_tracker(ws)
    today = date.today().isoformat()
    job = Job(title=args.title, company=args.company, link=args.link or "", source="Manual", location=args.location or "",
              description=args.description or "", posted_date=today, posting_ref=args.ref or "")
    p = Pipeline(ws, today=today)
    job.type = p.classify_type(job) or "Other"
    job.posting_language = p.posting_language(job)
    job.language_required = p.language_required(job, job.posting_language)
    job.work_mode = p.work_mode(job)
    job.score, job.fit, reasons = p.score(job)
    job.notes = "added manually; " + "; ".join(reasons)
    if not job.posting_ref:
        job.posting_ref = f"MAN-{t.next_id():04d}"
    jid = f"J{t.next_id():04d}"
    t.append_jobs([job.to_row(jid, today)])
    t.save()
    if args.status and args.status.lower() != "found":
        args.id, args.note, args.force, args.interview = jid, None, False, None
        cmd_track(args)
    else:
        t.refresh_review_queue()
        t.save()
    print(f"Added {jid}: {job.company}, {job.title} (fit {job.fit})")
    return 0


def cmd_watchlist(args) -> int:
    from .sources.ats import ATS, probe
    from .sources.base import Http
    ws = _ws(args)
    wl = ws.profile.setdefault("watchlist", [])
    if args.action == "list":
        for w in wl:
            print(f"  {'on ' if w.get('active', True) else 'off'}  {w['name']:<30} {w.get('ats') or '-':<16} {w.get('slug') or ''}")
        return 0
    if args.action == "remove":
        ws.profile["watchlist"] = [w for w in wl if w["name"].lower() != args.name.lower()]
        ws.save_profile()
        print(f"Removed {args.name}")
        return 0
    # add
    ats, slug = None, None
    if args.ats:
        if ":" not in args.ats or args.ats.split(":")[0] not in ATS:
            print(f"--ats must look like greenhouse:slug. Known systems: {', '.join(ATS)}")
            return 1
        ats, slug = args.ats.split(":", 1)
    else:
        print(f"Looking up {args.name} ...")
        found = probe(Http(delay=0.2), args.name)
        if found:
            ats, slug, n = found
            print(f"  found on {ats} as '{slug}' with {n} open roles")
        else:
            print("  careers system not detected. Add it with --ats greenhouse:slug (or lever, ashby, personio, "
                  "recruitee, smartrecruiters). The slug is in the company's careers page URL.")
    wl = [w for w in wl if w["name"].lower() != args.name.lower()]
    wl.append({"name": args.name, "active": True, "ats": ats or "", "slug": slug or "", "why": args.why or ""})
    ws.profile["watchlist"] = wl
    ws.save_profile()
    return 0


def cmd_assistants(args) -> int:
    from . import adapters
    ws = _ws(args)
    targets = args.targets or ws.get("assistant.targets", ["claude"])
    if args.targets:
        ws.profile.setdefault("assistant", {})["targets"] = targets
        ws.save_profile()
    for f in adapters.install(ws, targets):
        print(f"  wrote {f}")
    return 0


def cmd_schedule(args) -> int:
    from . import scheduler
    ws = _ws(args)
    if args.action == "install":
        for line in scheduler.install(ws):
            print(f"  scheduled {line}")
    elif args.action == "remove":
        scheduler.remove(ws)
        print("Removed JobPilot schedules.")
    else:
        lines = scheduler.show()
        print("\n".join(lines) if lines else "No JobPilot schedules installed.")
    return 0


def cmd_export(args) -> int:
    from .documents import to_docx, to_pdf
    src = Path(args.file).expanduser()
    if not src.exists():
        print(f"Not found: {src}")
        return 1
    fmts = ["docx", "pdf"] if args.format == "both" else [args.format]
    for f in fmts:
        out = src.with_suffix(f".{f}")
        (to_docx if f == "docx" else to_pdf)(src, out)
        print(f"  wrote {out}")
    return 0


def cmd_doctor(args) -> int:
    import platform
    import shutil
    from .search import enabled_sources
    ok = True
    print(f"JobPilot {__version__} on Python {platform.python_version()} ({platform.system()})")
    try:
        ws = _ws(args)
    except ConfigError as exc:
        print(f"[!] {exc}")
        return 1
    print(f"[ok] workspace {ws.path}")
    r = ws.path / "resume" / "resume.md"
    print(f"[{'ok' if r.exists() and r.stat().st_size > 200 else '!'}] resume text {r}")
    ok &= r.exists()
    try:
        from .tracker import open_tracker
        t = open_tracker(ws)
        print(f"[ok] tracker ({ws.get('tracker.backend', 'xlsx')}), {len(t.jobs())} jobs")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"[!] tracker: {exc}")
    srcs = enabled_sources(ws)
    print(f"[ok] sources: {', '.join(srcs) or 'none'}")
    for name, key in (("adzuna", "JOBPILOT_ADZUNA_APP_ID"), ("apify_linkedin", "JOBPILOT_APIFY_TOKEN")):
        if name in srcs and not ws.env.get(key):
            ok = False
            print(f"[!] {name} is on but {key} is missing in .env")
    if ws.get("inbox.enabled") and not ws.env.get("JOBPILOT_IMAP_PASSWORD"):
        ok = False
        print("[!] inbox is on but JOBPILOT_IMAP_PASSWORD is missing in .env")
    for t_ in ws.get("assistant.targets", []):
        exe = {"claude": "claude", "codex": "codex", "gemini": "gemini"}.get(t_)
        if exe:
            print(f"[{'ok' if shutil.which(exe) else '?'}] {t_} CLI {'found' if shutil.which(exe) else 'not on PATH'}")
    from . import scheduler
    try:
        lines = scheduler.show()
        print(f"[{'ok' if lines else '-'}] schedule: {len(lines)} entries")
    except Exception as exc:  # noqa: BLE001
        print(f"[-] schedule: {exc}")
    print("All good." if ok else "Fix the [!] items above, then run `jobpilot doctor` again.")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobpilot", description="AI job search copilot. Run `jobpilot setup` first.")
    p.add_argument("--version", action="version", version=f"jobpilot {__version__}")
    p.add_argument("--workspace", "-w", help="Workspace folder (default: the one chosen in setup)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="Interactive setup (safe to re-run)")
    s.add_argument("--answers", help="YAML file with answers for a non-interactive setup")
    s.add_argument("--no-search", action="store_true", help="Do not offer a first search at the end")
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("search", help="Find new postings and add them to the tracker")
    s.add_argument("--sources", nargs="*", help="Only these sources (arbeitnow bundesagentur adzuna watchlist apify_linkedin apify_xing)")
    s.add_argument("--dry-run", action="store_true", help="Show results without writing")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("inbox", help="Read recent mail (read only) and update statuses")
    s.add_argument("--days", type=int, default=2)
    s.add_argument("--force", action="store_true", help="Run even if inbox is disabled in profile.yaml")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(func=cmd_inbox)

    s = sub.add_parser("status", help="Pipeline overview and review queue")
    s.add_argument("--limit", type=int, default=15)
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("show", help="Show one tracked job")
    s.add_argument("id")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("track", help="Change a job's status, e.g. `jobpilot track J0012 Applied --note 'LinkedIn'`")
    s.add_argument("id")
    s.add_argument("status", help=", ".join(STATUSES))
    s.add_argument("--note")
    s.add_argument("--interview", help="Interview date and time, e.g. '2026-10-20 14:00'")
    s.add_argument("--force", action="store_true", help="Allow moving a status backwards")
    s.set_defaults(func=cmd_track)

    s = sub.add_parser("add", help="Add a job you found yourself")
    s.add_argument("--company", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--link")
    s.add_argument("--location")
    s.add_argument("--description")
    s.add_argument("--ref", help="Posting reference number")
    s.add_argument("--status", default="Found")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("watchlist", help="Manage companies watched on their own career pages")
    s.add_argument("action", choices=["add", "remove", "list"])
    s.add_argument("name", nargs="?", default="")
    s.add_argument("--ats", help="Skip detection, e.g. greenhouse:celonis or workday:tenant.wd3/SiteName")
    s.add_argument("--why")
    s.set_defaults(func=cmd_watchlist)

    s = sub.add_parser("assistants", help="(Re)write CLAUDE.md, AGENTS.md, GEMINI.md and skills from profile.yaml")
    s.add_argument("--targets", nargs="*", choices=["claude", "codex", "gemini", "projects"])
    s.set_defaults(func=cmd_assistants)

    s = sub.add_parser("schedule", help="Install, remove or show automatic runs")
    s.add_argument("action", choices=["install", "remove", "show"])
    s.set_defaults(func=cmd_schedule)

    s = sub.add_parser("export", help="Convert a Markdown document to DOCX or PDF")
    s.add_argument("file")
    s.add_argument("--format", choices=["docx", "pdf", "both"], default="docx")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("doctor", help="Check that everything is set up")
    s.set_defaults(func=cmd_doctor)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "cmd", None) == "watchlist" and args.action in ("add", "remove") and not args.name:
        print("Give a company name, e.g. jobpilot watchlist add \"Celonis\"")
        return 1
    try:
        return int(args.func(args) or 0)
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (KeyError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
