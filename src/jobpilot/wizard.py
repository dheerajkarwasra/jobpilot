"""Interactive setup: `jobpilot setup`.

Asks about the person, resume, targets, assistants, tracker and automation, then
builds the workspace. Re-running it on an existing workspace keeps your answers
as defaults. `jobpilot setup --answers answers.yaml` runs without questions.
"""
from __future__ import annotations

import getpass
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from . import adapters
from .config import DEFAULT_WORKSPACE, dump_yaml, load_defaults, remember_workspace, write_env

BANNED_DEFAULT = ["passionate", "synergy", "leverage", "dynamic", "results-driven", "cutting-edge", "spearheaded",
                  "rockstar", "ninja", "game-changer", "thrilled", "delve"]
RULES_DEFAULT = ["Plain, human sounding language with a direct tone",
                 "No em dashes and minimal punctuation",
                 "Short sentences, concrete facts, real numbers only"]
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "Native"]


# --- prompt helpers ----------------------------------------------------------
class Asker:
    def __init__(self, answers: Optional[Dict[str, Any]] = None):
        self.answers = answers
        self.interactive = answers is None

    def _in(self, prompt: str) -> str:
        try:
            return input(prompt)
        except EOFError:
            raise SystemExit("\nSetup needs an interactive terminal. Use `jobpilot setup --answers answers.yaml` instead.")

    def text(self, key: str, question: str, default: str = "", required: bool = False) -> str:
        if not self.interactive:
            v = self.answers.get(key, default)
            return "" if v is None else str(v)
        hint = f" [{default}]" if default else ""
        while True:
            v = self._in(f"{question}{hint}: ").strip() or default
            if v or not required:
                return v
            print("  This one is required.")

    def secret(self, key: str, question: str) -> str:
        if not self.interactive:
            return str(self.answers.get(key, "") or "")
        try:
            return getpass.getpass(f"{question} (hidden, Enter to skip): ").strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def yes(self, key: str, question: str, default: bool = True) -> bool:
        if not self.interactive:
            return bool(self.answers.get(key, default))
        d = "Y/n" if default else "y/N"
        v = self._in(f"{question} [{d}]: ").strip().lower()
        return default if not v else v.startswith("y") or v.startswith("j")

    def choice(self, key: str, question: str, options: Dict[str, str], default: str) -> str:
        if not self.interactive:
            return str(self.answers.get(key, default))
        keys = list(options)
        print(question)
        for i, k in enumerate(keys, 1):
            print(f"  {i}. {options[k]}{'  (default)' if k == default else ''}")
        while True:
            v = self._in("Choose a number: ").strip()
            if not v:
                return default
            if v.isdigit() and 1 <= int(v) <= len(keys):
                return keys[int(v) - 1]
            if v in options:
                return v
            print("  Please type one of the numbers.")

    def multi(self, key: str, question: str, options: Dict[str, str], default: List[str]) -> List[str]:
        if not self.interactive:
            return list(self.answers.get(key, default))
        keys = list(options)
        print(question + " (numbers separated by commas)")
        for i, k in enumerate(keys, 1):
            print(f"  {i}. {options[k]}{'  *' if k in default else ''}")
        while True:
            v = self._in(f"Your choice [{','.join(str(keys.index(d) + 1) for d in default)}]: ").strip()
            if not v:
                return default
            try:
                picks = [keys[int(x) - 1] for x in v.replace(" ", "").split(",") if x]
                return picks or default
            except (ValueError, IndexError):
                print("  Please type numbers from the list, like 1,3.")

    def items(self, key: str, question: str, default: List[str]) -> List[str]:
        if not self.interactive:
            return list(self.answers.get(key, default) or [])
        d = ", ".join(default)
        v = self._in(f"{question}\n  [{d[:160]}{'...' if len(d) > 160 else ''}]\n  > ").strip()
        if not v:
            return default
        if v.startswith("+"):
            return default + [x.strip() for x in v[1:].split(",") if x.strip()]
        return [x.strip() for x in v.split(",") if x.strip()]


def section(title: str, interactive: bool) -> None:
    if interactive:
        print(f"\n=== {title} ===")


# --- query building ------------------------------------------------------------
def build_queries(role_types: List[str], fields: List[str], defaults: Dict, local_lang: Optional[str]):
    en, local = [], []
    for f in fields:
        fd = defaults["fields"][f]
        for t in fd["en"][:2]:
            if "werkstudent" in role_types:
                en.append(f"Working Student {t}")
            if "internship" in role_types:
                en.append(f"{t} Intern")
            if "entry" in role_types:
                en.append(f"Junior {t}")
            if "thesis" in role_types:
                en.append(f"Thesis {t}")
            if "fulltime" in role_types:
                en.append(t)
        if local_lang == "german":
            for t in fd["de"][:1]:
                if "werkstudent" in role_types:
                    local.append(f"Werkstudent {t}")
                if "internship" in role_types:
                    local.append(f"Praktikum {t}")
                if "thesis" in role_types:
                    local.append(f"Abschlussarbeit {t}")
    dedup = lambda xs: list(dict.fromkeys(xs))  # noqa: E731
    return dedup(en)[:12], dedup(local)[:8]


# --- main --------------------------------------------------------------------------
def run(workspace: Optional[str] = None, answers_file: Optional[str] = None, skip_search: bool = False) -> Path:
    defaults = load_defaults()
    answers = yaml.safe_load(Path(answers_file).read_text(encoding="utf-8")) if answers_file else None
    a = Asker(answers)
    I = a.interactive  # noqa: E741

    if I:
        print("\nJobPilot setup. Press Enter to accept the value in [brackets]. You can change everything later\n"
              "in profile.yaml or by running `jobpilot setup` again.")

    section("Workspace", I)
    ws = Path(a.text("workspace", "Where should your job search folder live", workspace or str(DEFAULT_WORKSPACE))).expanduser()
    old: Dict[str, Any] = {}
    if (ws / "profile.yaml").exists():
        old = yaml.safe_load((ws / "profile.yaml").read_text(encoding="utf-8")) or {}
        if I:
            print("  Found an existing profile. Your previous answers are the defaults.")
    g = lambda dotted, d="": _get(old, dotted, d)  # noqa: E731

    section("Resume", I)
    resume_src = a.text("resume_path", "Path to your resume (.docx, .pdf, .md or .txt). Drag the file here",
                        g("resume.source", ""))
    resume_src = resume_src.strip().strip("'\"")
    resume_text, basics = "", {}
    if resume_src:
        from .documents import extract_text, guess_basics
        src = Path(resume_src).expanduser()
        if src.exists():
            resume_text = extract_text(src)
            basics = guess_basics(resume_text)
            if I:
                print(f"  Read {len(resume_text.split())} words from {src.name}.")
        elif I:
            print("  File not found. You can add it later to the resume/ folder and run `jobpilot setup` again.")

    section("About you", I)
    person = {
        "name": a.text("name", "Full name", g("person.name", basics.get("name", "")), required=True),
        "email": a.text("email", "Email", g("person.email", basics.get("email", ""))),
        "phone": a.text("phone", "Phone (optional)", g("person.phone", basics.get("phone", ""))),
        "location": a.text("location", "City and country you live in", g("person.location", "")),
        "linkedin": a.text("linkedin", "LinkedIn URL (optional)", g("person.linkedin", basics.get("linkedin", ""))),
        "github": a.text("github", "GitHub URL (optional)", g("person.github", basics.get("github", ""))),
        "portfolio": a.text("portfolio", "Portfolio or website (optional)", g("person.portfolio", "")),
    }
    about = a.text("about", "One or two lines about you and what you want next (optional)", g("about", ""))
    edu = [{
        "degree": a.text("degree", "Current or latest degree (e.g. M.Sc. Computer Science)", g("education.0.degree", "")),
        "school": a.text("school", "University", g("education.0.school", "")),
        "end": a.text("graduation", "Graduation (year or month/year)", g("education.0.end", "")),
    }]
    status = {
        "work_permit": a.text("work_permit", "Work permit or limits an employer should know "
                              "(e.g. 'Student visa, max 20h/week during semester', or leave empty)", g("status.work_permit", "")),
        "hours_per_week": a.text("hours_per_week", "Hours per week you can work (optional)", str(g("status.hours_per_week", "") or "")),
        "available_from": a.text("available_from", "Available from (optional, e.g. 2026-11)", g("status.available_from", "")),
    }

    section("Languages", I)
    langs: List[Dict[str, str]] = []
    if I:
        prev = g("languages", []) or [{"language": "English", "level": "C1"}]
        print("  Add each language you speak with a level: A1, A2, B1, B2, C1, C2 or Native.")
        print(f"  Current: {', '.join(l['language'] + ' ' + l['level'] for l in prev)}")
        raw = a._in("  Type like 'English C1, German A1' or Enter to keep: ").strip()
        if raw:
            for part in raw.split(","):
                bits = part.strip().rsplit(" ", 1)
                if len(bits) == 2:
                    langs.append({"language": bits[0].strip().capitalize(), "level": bits[1].strip().upper()})
        langs = langs or prev
    else:
        langs = answers.get("languages") or g("languages", None) or [{"language": "English", "level": "C1"}]

    section("What you are looking for", I)
    countries = {k: v["name"] for k, v in defaults["countries"].items()}
    country = a.choice("country", "Which country should JobPilot search in?", countries, g("search.country", "de"))
    cdef = defaults["countries"][country]
    local_lang = cdef.get("language")
    remote_ok = a.yes("remote_ok", "Include remote roles open to people in that country?", bool(g("search.remote_ok", True)))
    role_types = a.multi("role_types", "Which kinds of roles?", {k: v["label"] for k, v in defaults["role_types"].items()},
                         g("search.role_types", ["werkstudent", "internship", "entry"]))
    fields = a.multi("fields", "Which fields? Put your main focus first.", {k: v["label"] for k, v in defaults["fields"].items()},
                     g("search.fields", ["software", "ai"]))
    q_en, q_local = build_queries(role_types, fields, defaults, local_lang)
    q_en = a.items("queries_en", "Search queries in English (comma separated, '+x, y' to add)", g("search.queries_en", q_en) or q_en)
    if local_lang:
        q_local = a.items("queries_local", f"Search queries in {local_lang.capitalize()}", g("search.queries_local", q_local) or q_local)
    skills = a.items("skills", "Your core skills (used for scoring)", g("skills", basics.get("skills", [])[:15]))
    max_ok = "A2"
    if local_lang:
        user_level = next((l["level"] for l in langs if l["language"].lower() == local_lang), "none")
        max_ok = a.choice("max_local_language_level_ok",
                          f"Highest {local_lang.capitalize()} level a job may ask for and still be shown "
                          f"(your level: {user_level})",
                          {lv: lv for lv in CEFR_LEVELS[:6]}, g("search.max_local_language_level_ok",
                                                                user_level if user_level in CEFR_LEVELS else "A2"))
    exclude_title = a.items("exclude_title", "Skip jobs whose title contains", g("search.exclude_title", defaults["exclude_title_default"]))
    exclude_companies = a.items("exclude_companies", "Skip these companies (staffing agencies are a good start)",
                                g("search.exclude_companies", defaults["staffing_agencies_default"]))

    section("Writing style", I)
    rules = a.items("writing_rules", "Rules for everything written for you", g("writing.rules", RULES_DEFAULT))
    banned = a.items("banned_words", "Words to never use", g("writing.banned_words", BANNED_DEFAULT))

    section("AI assistant", I)
    detected = [t for t, exe in (("claude", "claude"), ("codex", "codex"), ("gemini", "gemini")) if shutil.which(exe)]
    targets = a.multi("assistants", "Which assistants do you use? (detected ones are marked *)", adapters.TARGETS,
                      g("assistant.targets", detected or ["claude"]))

    section("Tracker", I)
    backend = a.choice("tracker_backend", "Where should applications be tracked?",
                       {"xlsx": "Excel file on this computer (simplest)", "gsheets": "Google Sheets (needs a service account, see docs)"},
                       g("tracker.backend", "xlsx"))
    tracker = {"backend": backend, "xlsx_path": "tracker/Job_Search_Tracker.xlsx"}
    if backend == "gsheets":
        tracker["gsheet_id"] = a.text("gsheet_id", "Spreadsheet ID (the long part of the sheet URL)", g("tracker.gsheet_id", ""), True)
        tracker["service_account_json"] = a.text("service_account_json", "Path to the service account JSON key",
                                                 g("tracker.service_account_json", ""), True)

    section("Job sources", I)
    if I:
        print("  Free sources are always on: " + ("Arbeitnow, Bundesagentur (Germany), " if country == "de" else "")
              + "and your company watchlist.")
    env: Dict[str, str] = {}
    use_adzuna = a.yes("adzuna", "Add Adzuna (free key from developer.adzuna.com, many countries)?", bool(g("sources.adzuna", False)))
    if use_adzuna:
        env["JOBPILOT_ADZUNA_APP_ID"] = a.text("adzuna_app_id", "  Adzuna app_id", "")
        env["JOBPILOT_ADZUNA_APP_KEY"] = a.secret("adzuna_app_key", "  Adzuna app_key")
    use_apify = a.yes("apify", "Add LinkedIn (and Xing) through Apify? Uses Apify credits, free plan has about 5 USD per month",
                      bool(g("sources.apify_linkedin", False)))
    budget = 4.0
    if use_apify:
        env["JOBPILOT_APIFY_TOKEN"] = a.secret("apify_token", "  Apify API token (apify.com > Settings > API & Integrations)")
        budget = float(a.text("apify_budget", "  Monthly Apify budget in USD", str(g("sources.apify_monthly_budget_usd", 4.0))))
    watch_names = a.items("watchlist", "Companies to watch directly on their career pages (comma separated, optional)",
                          [w["name"] for w in (g("watchlist", []) or [])])

    section("Automation", I)
    schedule_on = a.yes("schedule", "Run the job search automatically on this computer?",
                        bool(g("schedule.search_every_hours", 6)))
    every = int(a.text("search_every_hours", "  Every how many hours", str(g("schedule.search_every_hours", 6)))) if schedule_on else 0
    inbox_on = a.yes("inbox", "Check your mailbox for replies once a day (read only, needs an app password)?",
                     bool(g("inbox.enabled", False)))
    inbox = {"enabled": inbox_on}
    if inbox_on:
        provider = a.choice("mail_provider", "Mail provider", {"gmail": "Gmail", "outlook": "Outlook / Microsoft 365",
                                                                 "other": "Other IMAP"}, "gmail")
        host = {"gmail": "imap.gmail.com", "outlook": "outlook.office365.com"}.get(provider) or \
            a.text("imap_host", "  IMAP server", g("inbox.imap_host", ""))
        inbox.update({"imap_host": host, "username": a.text("imap_user", "  Mail address", g("inbox.username", person["email"]))})
        env["JOBPILOT_IMAP_PASSWORD"] = a.secret("imap_password", "  App password (not your normal password)")
    inbox_time = a.text("inbox_time", "  Daily inbox check time (HH:MM)", g("schedule.inbox_daily_at", "07:52")) if inbox_on else "07:52"

    # --- build -----------------------------------------------------------------
    primary = defaults["fields"][fields[0]]["keywords"] if fields else []
    core = sorted({k for f in fields[1:] for k in defaults["fields"][f]["keywords"]} | {s.lower() for s in skills[:12]})
    must = sorted({k for f in fields for k in defaults["fields"][f]["keywords"]} | {s.lower() for s in skills[:12]})
    profile: Dict[str, Any] = {
        "version": 1,
        "person": person,
        "about": about,
        "education": edu,
        "status": {k: v for k, v in status.items() if v},
        "languages": langs,
        "skills": skills,
        "resume": {"source": resume_src, "original": "", "text": "resume/resume.md"},
        "search": {
            "country": country,
            "remote_ok": remote_ok,
            "role_types": role_types,
            "fields": fields,
            "queries_en": q_en,
            "queries_local": q_local,
            "local_language": local_lang,
            "max_local_language_level_ok": max_ok,
            "max_age_days": int(g("search.max_age_days", 3)),
            "must_match_any": must,
            "exclude_title": exclude_title,
            "exclude_companies": exclude_companies,
            "exclude_description": g("search.exclude_description", defaults["exclude_description_default"]),
            "location_keywords": g("search.location_keywords", cdef.get("location_keywords", [])),
        },
        "scoring": {
            "keywords": {"primary": primary, "core": [c for c in core if c not in primary],
                         "secondary": g("scoring.keywords.secondary", ["docker", "git", "linux", "cloud", "ci/cd", "sql"])},
            "penalize_fulltime": bool(g("scoring.penalize_fulltime", bool(status.get("work_permit")))),
            "weights": g("scoring.weights", {}),
        },
        "watchlist": [],
        "writing": {"rules": rules, "banned_words": banned, "cover_letter_paragraphs": g("writing.cover_letter_paragraphs", "3 to 4")},
        "assistant": {"targets": targets},
        "tracker": tracker,
        "sources": {
            "arbeitnow": country in ("de", "at", "ch"),
            "bundesagentur": country == "de",
            "adzuna": use_adzuna,
            "watchlist": True,
            "apify_linkedin": use_apify,
            "apify_xing": use_apify and country in ("de", "at", "ch"),
            "apify_monthly_budget_usd": budget,
            "apify_run_hours": g("sources.apify_run_hours", [6, 18]),
            "arbeitnow_pages": int(g("sources.arbeitnow_pages", 5)),
        },
        "schedule": {"search_every_hours": every, "inbox_daily_at": inbox_time},
        "inbox": inbox,
    }

    # keep settings the wizard does not ask about (hand edits in profile.yaml survive a re-run)
    profile = _merge(old or {}, profile)

    # --- write workspace ----------------------------------------------------------
    for d in ["resume", "tracker", "applications", "job-descriptions", "logs", "exports"]:
        (ws / d).mkdir(parents=True, exist_ok=True)
    if resume_src and Path(resume_src).expanduser().exists():
        src = Path(resume_src).expanduser()
        dest = ws / "resume" / src.name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        profile["resume"]["original"] = f"resume/{src.name}"
        (ws / "resume" / "resume.md").write_text(resume_text, encoding="utf-8")
    elif (ws / "resume" / "resume.md").exists():
        profile["resume"]["original"] = g("resume.original", "")

    # watchlist: keep old ATS info, probe new names
    old_watch = {w["name"].lower(): w for w in (g("watchlist", []) or [])}
    new_names = [n for n in watch_names if n.lower() not in old_watch]
    watch = [old_watch[n.lower()] for n in watch_names if n.lower() in old_watch]
    if new_names:
        from .sources.ats import probe
        from .sources.base import Http
        http = Http(delay=0.2)
        for n in new_names:
            if I:
                print(f"  Looking up {n} ...", end=" ", flush=True)
            try:
                found = probe(http, n) if (I or answers.get("probe_watchlist", True)) else None
            except Exception:  # noqa: BLE001
                found = None
            if found:
                watch.append({"name": n, "active": True, "ats": found[0], "slug": found[1], "why": ""})
                if I:
                    print(f"{found[0]} ({found[2]} open roles)")
            else:
                watch.append({"name": n, "active": True, "ats": "", "slug": "", "why": "careers system not detected"})
                if I:
                    print("not found (add ats and slug in profile.yaml by hand)")
    profile["watchlist"] = watch

    (ws / "profile.yaml").write_text(
        "# JobPilot profile. Edit freely, then run `jobpilot assistants` to refresh the assistant files.\n"
        + dump_yaml(profile), encoding="utf-8")
    write_env(ws, env)
    gi = ws / ".gitignore"
    if not gi.exists():
        gi.write_text(".env\nlogs/\n*.json\n", encoding="utf-8")
    remember_workspace(ws)

    from .config import Workspace
    wsobj = Workspace(ws)
    from .tracker import open_tracker
    t = open_tracker(wsobj)
    t.sync_watchlist(watch, date.today().isoformat())
    t.save()
    written = adapters.install(wsobj, targets)

    sched_msg = []
    if schedule_on or inbox_on:
        if not I or a.yes("install_schedule", "Install the schedule now?", True):
            try:
                from . import scheduler
                sched_msg = scheduler.install(wsobj)
            except Exception as exc:  # noqa: BLE001
                sched_msg = [f"could not install schedule: {exc}. Run `jobpilot schedule install` later."]

    print(f"\nDone. Workspace: {ws}")
    print(f"  Tracker: {wsobj.tracker_path if backend == 'xlsx' else 'Google Sheet ' + tracker.get('gsheet_id', '')}")
    print(f"  Assistant files: {', '.join(sorted({w.split('/')[0] for w in written}))}")
    for m in sched_msg:
        print(f"  Schedule: {m}")
    print(_next_steps(ws, targets))

    if not skip_search and I and a.yes("first_search", "Run the first job search now?", True):
        from .search import run_search
        run_search(wsobj)
    return ws


def _next_steps(ws: Path, targets: List[str]) -> str:
    lines = ["\nNext steps:"]
    if "claude" in targets:
        lines.append(f"  Claude Code:  cd \"{ws}\" && claude     then type /jobpilot-search or /jobpilot-apply <link>")
    if "codex" in targets:
        lines.append(f"  Codex:        cd \"{ws}\" && codex      then type $jobpilot-search or $jobpilot-apply <link>")
    if "gemini" in targets:
        lines.append(f"  Gemini CLI:   cd \"{ws}\" && gemini     then type /jobpilot-search or /jobpilot-apply <link>")
    if "projects" in targets:
        lines.append(f"  Projects:     paste {ws / 'exports' / 'PROJECT_INSTRUCTIONS.md'} into your project instructions")
    if "claude_app" in targets:
        lines.append(f"  Claude app:   follow {ws / 'exports' / 'CLAUDE_APP_SETUP.md'} (connectors and scheduled tasks)")
    lines.append("  Anytime:      jobpilot status   |   jobpilot search   |   jobpilot doctor")
    return "\n".join(lines)


def _get(d: Dict, dotted: str, default: Any = "") -> Any:
    node: Any = d
    for part in dotted.split("."):
        if isinstance(node, list):
            try:
                node = node[int(part)]
                continue
            except (ValueError, IndexError):
                return default
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node if node not in (None, "") else default


def _merge(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge where values from `new` win and keys only in `old` are kept."""
    out = dict(old)
    for k, v in new.items():
        out[k] = _merge(old[k], v) if isinstance(v, dict) and isinstance(old.get(k), dict) else v
    return out
