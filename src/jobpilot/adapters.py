"""Write assistant integration files into the workspace.

Targets:
  claude    Claude Code      CLAUDE.md + .claude/skills/<skill>/SKILL.md      invoke: /jobpilot-apply J0012
  codex     OpenAI Codex CLI AGENTS.md + .agents/skills/<skill>/SKILL.md      invoke: $jobpilot-apply J0012
  gemini    Gemini CLI       GEMINI.md + .agents/skills + .gemini/commands    invoke: /jobpilot-apply J0012
  projects  Claude.ai / ChatGPT Projects: exports/PROJECT_INSTRUCTIONS.md to paste into the project settings
  claude_app Claude app with connectors: exports/CLAUDE_APP_SETUP.md with Sheets, Gmail and scheduled task prompts
All skills follow the open Agent Skills format (SKILL.md with name + description).
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List

from .config import Workspace, read_template
from .models import APPLICATION_COLUMNS, JOB_COLUMNS, RUNLOG_COLUMNS, STATUSES, WATCHLIST_COLUMNS

SKILLS = ["jobpilot-apply", "jobpilot-review", "jobpilot-search", "jobpilot-track"]
TARGETS = {
    "claude": "Claude Code",
    "codex": "OpenAI Codex CLI",
    "gemini": "Gemini CLI",
    "projects": "Claude.ai or ChatGPT Projects (copy and paste)",
    "claude_app": "Claude app with Google Sheets, Gmail and scheduled tasks (runs in the cloud)",
}
_VAR = re.compile(r"\{\{(\w+)\}\}")


def cli_command(ws: Workspace) -> str:
    exe = shutil.which("jobpilot")
    base = f'"{exe}"' if exe and " " in exe else (exe or f'"{sys.executable}" -m jobpilot')
    return base


def _list(items) -> str:
    return ", ".join(str(i) for i in items if i)


def variables(ws: Workspace) -> Dict[str, str]:
    p = ws.profile
    person = p.get("person", {}) or {}
    defaults = ws.defaults
    langs = p.get("languages", []) or []
    lang_text = _list(f"{l.get('language')} ({l.get('level')})" for l in langs)
    local = ws.get("search.local_language") or ws.country.get("language") or ""
    local_cap = local.capitalize() if local else "the local language"
    role_labels = [defaults["role_types"][r]["label"] for r in ws.get("search.role_types", []) if r in defaults["role_types"]]
    fields = [defaults["fields"][f]["label"] for f in ws.get("search.fields", []) if f in defaults["fields"]]
    country_name = ws.country.get("name", ws.get("search.country", ""))
    edu = p.get("education", []) or []
    edu_lines = [f"{e.get('degree', '')}, {e.get('school', '')} ({e.get('end', '') or 'ongoing'})".strip(", ") for e in edu]
    status = p.get("status", {}) or {}
    links = _list([person.get("linkedin"), person.get("github"), person.get("portfolio")])
    summary = [
        f"- Name: {person.get('name', '')}" + (f", based in {person.get('location')}" if person.get("location") else ""),
        *(f"- Education: {e}" for e in edu_lines),
        f"- Work permit and availability: {status.get('work_permit') or 'no restrictions stated'}"
        + (f", up to {status.get('hours_per_week')} hours per week" if status.get("hours_per_week") else "")
        + (f", available from {status.get('available_from')}" if status.get("available_from") else ""),
        f"- Languages: {lang_text or 'not set'}",
        f"- Looking for: {_list(role_labels) or 'not set'} in {_list(fields) or 'their field'}, in {country_name}"
        + (" or remote" if ws.get("search.remote_ok", True) else ""),
        f"- Core skills: {_list(p.get('skills', []) or []) or 'see resume'}",
    ]
    if links:
        summary.append(f"- Links: {links}")
    if p.get("about"):
        summary.append(f"- In their words: {p['about']}")
    rules = (p.get("writing", {}) or {}).get("rules") or []
    banned = (p.get("writing", {}) or {}).get("banned_words") or []
    rule_lines = [f"- {r}" for r in rules]
    if banned:
        rule_lines.append(f"- Never use these words: {_list(banned)}.")
    user_level = next((str(l.get("level")) for l in langs if str(l.get("language", "")).lower() == local.lower()), "none") \
        if local else ""
    red = []
    if status.get("work_permit"):
        red.append(f"work permit or hours limits ({status.get('work_permit')})")
    if local:
        red.append(f"{local_cap} language requirement (user level: {user_level})")
    red += ["location and relocation", "experience level mismatch"]
    tracker_desc = (f"the Google Sheet https://docs.google.com/spreadsheets/d/{ws.get('tracker.gsheet_id')}"
                    if ws.get("tracker.backend") == "gsheets" else f"the Excel file `{ws.get('tracker.xlsx_path', 'tracker/Job_Search_Tracker.xlsx')}`")
    resume_file = ws.get("resume.original", "resume/")
    return {
        "name": (person.get("name") or "the user").replace('"', "'"),
        "profile_summary": "\n".join(summary),
        "resume_file": resume_file,
        "cli": cli_command(ws),
        "tracker_desc": tracker_desc,
        "red_flags": "; ".join(red) + ".",
        "writing_rules": "\n".join(rule_lines) or "- Plain, direct language.",
        "writing_rules_inline": " ".join(r.rstrip(".") + "." for r in rules) + (f" Avoid: {_list(banned)}." if banned else ""),
        "cover_letter_paragraphs": str((p.get("writing", {}) or {}).get("cover_letter_paragraphs", "3 to 4")),
        "language_rule": (f"The user speaks {lang_text}. Mention their {local_cap} level only when the description asks about "
                          f"language, and never claim a higher level." if local else f"The user speaks {lang_text}."),
        "permit_rule": (f"Mention the work permit or hours limit ({status.get('work_permit')}) only when it matters for the "
                        f"role type, for example a full time role." if status.get("work_permit")
                        else "There are no work permit limits to mention."),
        "targets": _list(role_labels) + (f" in {_list(fields)}" if fields else ""),
        "country": country_name,
        "local_language": local_cap,
        "commands_line": "",
        "args": "",
    }


def app_variables(ws: Workspace) -> Dict[str, str]:
    """Extra values for the Claude app guide (scheduled task prompts)."""
    p = ws.profile
    kws = ws.get("scoring.keywords", {}) or {}
    country = ws.get("search.country", "de")
    sources = []
    if country in ("de", "at", "ch"):
        sources.append("- Arbeitnow API: https://www.arbeitnow.com/api/job-board-api (pages 1 to 5)")
    if country == "de":
        sources.append("- Bundesagentur Jobsuche API: https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs "
                       "with header X-API-Key: jobboerse-jobsuche, params was=<query>&wo=Deutschland&veroeffentlichtseit=<days>")
    watch = [w for w in (p.get("watchlist") or []) if w.get("active", True)]
    if watch:
        sources.append("- Company career APIs: " + _list(f"{w['name']} ({w['ats']}: {w['slug']})" if w.get("ats") else f"{w['name']} (find their careers page)"
                                                      for w in watch))
    sources.append("- The Indeed connector, if connected")
    if ws.get("sources.apify_linkedin"):
        sources.append("- Apify LinkedIn and Xing scrapers, at most twice a day, within "
                       f"{ws.get('sources.apify_monthly_budget_usd', 4)} USD per month")
    langs = p.get("languages", []) or []
    every = int(ws.get("schedule.search_every_hours", 6) or 6)
    return {
        "job_columns": _list(JOB_COLUMNS),
        "application_columns": _list(APPLICATION_COLUMNS),
        "runlog_columns": _list(RUNLOG_COLUMNS),
        "watchlist_columns": _list(WATCHLIST_COLUMNS),
        "statuses": _list(STATUSES),
        "every_hours": str(every),
        "inbox_time": str(ws.get("schedule.inbox_daily_at", "07:52")),
        "remote_text": " or remote" if ws.get("search.remote_ok", True) else "",
        "languages": _list(f"{l.get('language')} {l.get('level')}" for l in langs) or "English",
        "skills": _list((p.get("skills") or [])[:15]) or "see resume",
        "max_age": str(ws.get("search.max_age_days", 3)),
        "queries_en": "; ".join(ws.get("search.queries_en", []) or []) or "none",
        "queries_local": "; ".join(ws.get("search.queries_local", []) or []) or "none",
        "source_lines": "\n   ".join(sources),
        "exclude_title": _list(ws.get("search.exclude_title", []) or []) or "nothing",
        "exclude_companies": _list(ws.get("search.exclude_companies", []) or []) or "none",
        "max_level": str(ws.get("search.max_local_language_level_ok", "A2")),
        "primary_keywords": " / ".join(kws.get("primary", [])[:8]) or "your main field",
        "core_keywords": " / ".join(kws.get("core", [])[:10]) or "your core skills",
        "fulltime_note": " (work permit limits)" if ws.get("scoring.penalize_fulltime", False) else "",
    }


def render(text: str, vars_: Dict[str, str]) -> str:
    return _VAR.sub(lambda m: vars_.get(m.group(1), m.group(0)), text)


def _strip_frontmatter_keys(skill: str, keep=("name", "description")) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", skill, re.S)
    if not m:
        return skill
    lines = [l for l in m.group(1).splitlines() if l.split(":", 1)[0].strip() in keep]
    return "---\n" + "\n".join(lines) + "\n---\n" + skill[m.end():]


def _body(skill: str) -> str:
    m = re.match(r"^---\n.*?\n---\n", skill, re.S)
    return skill[m.end():] if m else skill


def _description(skill: str) -> str:
    m = re.search(r"^description:\s*(.+)$", skill, re.M)
    return m.group(1).strip().strip('"') if m else ""


def install(ws: Workspace, targets: List[str]) -> List[str]:
    written: List[str] = []
    base = variables(ws)
    instructions_t = read_template("instructions.md")
    skills_t = {s: read_template(f"skills/{s}.md") for s in SKILLS}

    def write(rel: str, content: str) -> None:
        path = ws.path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)

    if "claude" in targets:
        v = dict(base, commands_line="`/jobpilot-apply <job>`, `/jobpilot-review`, `/jobpilot-search`, `/jobpilot-track <update>`.",
                 args="$ARGUMENTS")
        write("CLAUDE.md", render(instructions_t, v))
        for s, t in skills_t.items():
            write(f".claude/skills/{s}/SKILL.md", render(t, v))

    if "codex" in targets or "gemini" in targets:
        v = dict(base, args="the user's message that invoked this skill")
        for s, t in skills_t.items():
            write(f".agents/skills/{s}/SKILL.md", _strip_frontmatter_keys(render(t, v)))

    if "codex" in targets:
        v = dict(base, commands_line="type `$jobpilot-apply <job>`, `$jobpilot-review`, `$jobpilot-search` or "
                                     "`$jobpilot-track <update>`, or just describe the task and the matching skill loads.")
        write("AGENTS.md", render(instructions_t, v))

    if "gemini" in targets:
        v = dict(base, commands_line="`/jobpilot-apply <job>`, `/jobpilot-review`, `/jobpilot-search`, `/jobpilot-track <update>`.",
                 args="{{args}}")
        write("GEMINI.md", render(instructions_t, v))
        for s, t in skills_t.items():
            rendered = render(t, v)
            desc = _description(rendered).replace('"', "'")
            body = _body(rendered).replace("'''", "'")
            write(f".gemini/commands/{s}.toml", f'description = "{desc}"\nprompt = \'\'\'\n{body}\n\'\'\'\n')

    if "claude_app" in targets:
        targets = list(targets) + (["projects"] if "projects" not in targets else [])
        write("exports/CLAUDE_APP_SETUP.md", render(read_template("claude_app.md"), dict(base, **app_variables(ws))))

    if "projects" in targets:
        v = dict(base, commands_line="none (this is a chat project).", cli="(not available in chat projects)")
        text = render(instructions_t, v)
        # Remove the CLI section, which only applies to coding assistants.
        text = re.sub(r"## What JobPilot gives you.*?(?=## Workflow)", "## Tracking\nThe user tracks applications in their "
                      "own spreadsheet. When they say they applied, remind them to update it.\n\n", text, flags=re.S)
        text = text.replace("run `(not available in chat projects) export` for DOCX or PDF", "offer the text ready to paste")
        text = re.sub(r".*\(not available in chat projects\).*\n", "", text)
        header = ("<!-- Paste everything below into your Claude.ai or ChatGPT Project instructions. "
                  "Upload resume/resume.md (or your original resume) as a project file. -->\n\n")
        write("exports/PROJECT_INSTRUCTIONS.md", header + text)
    return written
