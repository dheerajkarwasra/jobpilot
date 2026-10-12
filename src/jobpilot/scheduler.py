"""Install or remove scheduled runs: cron on macOS/Linux, Task Scheduler on Windows.

Your computer must be on and awake at the scheduled time. Missed runs are not a
problem: each search looks back a few days and skips anything already tracked.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from .config import Workspace

MARK = "# jobpilot"


def _cmd(ws: Workspace, task: str) -> str:
    py = sys.executable
    log = ws.path / "logs" / f"{task}.log"
    (ws.path / "logs").mkdir(exist_ok=True)
    return f'"{py}" -m jobpilot --workspace "{ws.path}" {task} --quiet >> "{log}" 2>&1'


def planned(ws: Workspace) -> List[Tuple[str, str, str]]:
    """(name, cron expression, command)"""
    out = []
    every = int(ws.get("schedule.search_every_hours", 6) or 0)
    if every:
        out.append(("search", f"47 */{every} * * *", _cmd(ws, "search")))
    if ws.get("inbox.enabled", False):
        hh, mm = str(ws.get("schedule.inbox_daily_at", "07:52")).split(":")
        out.append(("inbox", f"{int(mm)} {int(hh)} * * *", _cmd(ws, "inbox")))
    return out


def _crontab_read() -> List[str]:
    try:
        res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("crontab not found. Install cron or schedule `jobpilot search` yourself.") from exc
    return res.stdout.splitlines() if res.returncode == 0 else []


def _crontab_write(lines: List[str]) -> None:
    text = "\n".join(lines).strip() + "\n"
    subprocess.run(["crontab", "-"], input=text, text=True, check=True)


def install(ws: Workspace) -> List[str]:
    items = planned(ws)
    if platform.system() == "Windows":
        return _install_windows(ws, items)
    lines = [l for l in _crontab_read() if MARK not in l]
    for name, expr, cmd in items:
        lines.append(f"{expr} {cmd} {MARK}:{name}:{ws.path}")
    _crontab_write(lines)
    return [f"{name}: {expr}" for name, expr, _ in items]


def remove(ws: Workspace) -> None:
    if platform.system() == "Windows":
        for name in ("search", "inbox"):
            subprocess.run(["schtasks", "/Delete", "/TN", f"JobPilot {name}", "/F"], capture_output=True)
        return
    lines = [l for l in _crontab_read() if MARK not in l]
    _crontab_write(lines)


def show() -> List[str]:
    if platform.system() == "Windows":
        res = subprocess.run(["schtasks", "/Query", "/FO", "LIST"], capture_output=True, text=True)
        return [l for l in res.stdout.splitlines() if "JobPilot" in l]
    return [l for l in _crontab_read() if MARK in l]


def _install_windows(ws: Workspace, items) -> List[str]:
    done = []
    for name, expr, cmd in items:
        if name == "search":
            every = int(ws.get("schedule.search_every_hours", 6))
            args = ["/SC", "HOURLY", "/MO", str(every)]
        else:
            args = ["/SC", "DAILY", "/ST", str(ws.get("schedule.inbox_daily_at", "07:52"))]
        tr = f'cmd /c {cmd}'
        subprocess.run(["schtasks", "/Create", "/TN", f"JobPilot {name}", "/TR", tr, *args, "/F"], check=True,
                       capture_output=True)
        done.append(f"{name}: {' '.join(args)}")
    return done
