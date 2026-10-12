"""Tracker backends: local Excel file (default) or Google Sheets (optional)."""
from __future__ import annotations

from ..config import Workspace
from .base import Tracker


def open_tracker(ws: Workspace) -> Tracker:
    backend = ws.get("tracker.backend", "xlsx")
    if backend == "gsheets":
        from .gsheets import GSheetsTracker
        return GSheetsTracker(ws)
    from .xlsx import XlsxTracker
    return XlsxTracker(ws)
