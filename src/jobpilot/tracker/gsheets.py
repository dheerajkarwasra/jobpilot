"""Google Sheets tracker (optional).

Setup: create a Google Cloud service account, download its JSON key, share your
spreadsheet with the service account email as Editor. See docs/GOOGLE_SHEETS.md.
Install extras: pip install "jobpilot[gsheets]"
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..config import Workspace
from ..models import APPLICATION_COLUMNS, JOB_COLUMNS, RUNLOG_COLUMNS, WATCHLIST_COLUMNS
from .base import DASH_START_ROW, HOW_TO, SHEETS, Tracker, col_letter, dashboard_cells

HEADERS = {"Jobs": JOB_COLUMNS, "Applications": APPLICATION_COLUMNS, "Run Log": RUNLOG_COLUMNS,
           "Watchlist": WATCHLIST_COLUMNS,
           "Review Queue": ["ID", "Fit", "Score", "Company", "Title", "Posting Ref", "Type", "Location",
                            "Language Required", "Posted Date", "Link"]}


class GSheetsTracker(Tracker):
    def __init__(self, ws: Workspace, client: Any = None):
        super().__init__(ws)
        if client is None:
            try:
                import gspread  # noqa: F401
            except ImportError as exc:
                raise RuntimeError('Google Sheets support needs: pip install "jobpilot[gsheets]"') from exc
            import gspread
            key_file = ws.get("tracker.service_account_json")
            if not key_file:
                raise RuntimeError("tracker.service_account_json is not set in profile.yaml")
            from pathlib import Path
            kp = Path(str(key_file)).expanduser()
            client = gspread.service_account(filename=str(kp if kp.is_absolute() else ws.path / kp))
        sheet_id = ws.get("tracker.gsheet_id")
        if not sheet_id:
            raise RuntimeError("tracker.gsheet_id is not set in profile.yaml")
        self.sh = client.open_by_key(sheet_id)
        self._cache: Dict[str, List[List[Any]]] = {}
        self._ensure_structure()

    def _ws(self, name: str):
        return self.sh.worksheet(name)

    def _ensure_structure(self) -> None:
        existing = {w.title for w in self.sh.worksheets()}
        for name in SHEETS:
            if name not in existing:
                cols = len(HEADERS.get(name, [])) or 8
                w = self.sh.add_worksheet(title=name, rows=2000, cols=max(cols, 8))
                if name in HEADERS:
                    w.update(range_name="A1", values=[HEADERS[name]])
                    w.freeze(rows=1)
                if name == "Dashboard":
                    vals = [["Job Search Dashboard"], ["Built by JobPilot"], [""]]
                    for label, formula in dashboard_cells():
                        vals.append([label, formula or ""])
                    w.update(range_name="A1", values=vals, value_input_option="USER_ENTERED")
                    w.update(range_name=f"D{DASH_START_ROW}", values=[[h] for h in HOW_TO])
        # remove the default empty "Sheet1" if we created everything else
        for w in self.sh.worksheets():
            if w.title in ("Sheet1", "Tabelle1") and len(self.sh.worksheets()) > len(SHEETS):
                try:
                    self.sh.del_worksheet(w)
                except Exception:  # noqa: BLE001
                    pass

    def _rows(self, sheet: str) -> List[List[Any]]:
        if sheet not in self._cache:
            self._cache[sheet] = self._ws(sheet).get_all_values()
        return self._cache[sheet]

    def _append(self, sheet: str, rows: List[List[Any]]) -> None:
        self._ws(sheet).append_rows(rows, value_input_option="RAW", table_range="A1")
        self._cache.pop(sheet, None)

    def _update_cells(self, sheet: str, updates: List[Tuple[int, int, Any]]) -> None:
        if not updates:
            return
        data = [{"range": f"{col_letter(c)}{r}", "values": [[v]]} for r, c, v in updates]
        self._ws(sheet).batch_update(data, value_input_option="RAW")
        self._cache.pop(sheet, None)

    def _replace_sheet(self, sheet: str, header: List[str], rows: List[List[Any]]) -> None:
        w = self._ws(sheet)
        w.clear()
        w.update(range_name="A1", values=[header] + rows, value_input_option="RAW")
        self._cache.pop(sheet, None)
