"""Workspace, profile and secrets handling.

Layout of a workspace (default ~/JobPilot):
    profile.yaml        everything about the user and the search
    .env                secrets (API keys, mail app password), chmod 600
    resume/             original resume plus resume.md text version
    tracker/            Job_Search_Tracker.xlsx (local backend)
    applications/       generated cover letters, resumes, messages
    job-descriptions/   saved postings
    logs/               scheduled run logs
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

try:  # Python 3.9+
    from importlib.resources import files as _res_files
except ImportError:  # pragma: no cover
    _res_files = None

POINTER_FILE = Path(os.environ.get("JOBPILOT_CONFIG_DIR", Path.home() / ".config" / "jobpilot")) / "workspace"
DEFAULT_WORKSPACE = Path.home() / "JobPilot"


class ConfigError(RuntimeError):
    pass


def load_defaults() -> Dict[str, Any]:
    if _res_files is not None:
        text = (_res_files("jobpilot") / "data" / "defaults.yaml").read_text(encoding="utf-8")
    else:  # pragma: no cover
        text = (Path(__file__).parent / "data" / "defaults.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


def read_template(name: str) -> str:
    if _res_files is not None:
        return (_res_files("jobpilot") / "templates" / name).read_text(encoding="utf-8")
    return (Path(__file__).parent / "templates" / name).read_text(encoding="utf-8")  # pragma: no cover


def find_workspace(explicit: Optional[str] = None) -> Path:
    """Resolve the workspace: --workspace flag, JOBPILOT_HOME, pointer file, cwd, default."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if os.environ.get("JOBPILOT_HOME"):
        candidates.append(Path(os.environ["JOBPILOT_HOME"]).expanduser())
    if POINTER_FILE.exists():
        candidates.append(Path(POINTER_FILE.read_text(encoding="utf-8").strip()).expanduser())
    candidates.append(Path.cwd())
    candidates.append(DEFAULT_WORKSPACE)
    for c in candidates:
        if (c / "profile.yaml").exists():
            return c.resolve()
    if explicit:
        return Path(explicit).expanduser().resolve()
    raise ConfigError("No JobPilot workspace found. Run `jobpilot setup` first, "
                      "or pass --workspace PATH / set JOBPILOT_HOME.")


def remember_workspace(ws: Path) -> None:
    POINTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    POINTER_FILE.write_text(str(ws.resolve()), encoding="utf-8")


def load_env(ws: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    p = ws / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    # Real environment variables win, so CI and power users can override.
    for k in list(env) + ["JOBPILOT_ADZUNA_APP_ID", "JOBPILOT_ADZUNA_APP_KEY", "JOBPILOT_APIFY_TOKEN",
                          "JOBPILOT_IMAP_PASSWORD"]:
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def write_env(ws: Path, values: Dict[str, str]) -> None:
    p = ws / ".env"
    existing = load_env(ws) if p.exists() else {}
    existing.update({k: v for k, v in values.items() if v})
    lines = ["# JobPilot secrets. Never commit this file."]
    lines += [f"{k}={v}" for k, v in sorted(existing.items())]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:  # Windows
        pass


class Workspace:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.profile_path = self.path / "profile.yaml"
        if not self.profile_path.exists():
            raise ConfigError(f"profile.yaml not found in {self.path}")
        self.profile: Dict[str, Any] = yaml.safe_load(self.profile_path.read_text(encoding="utf-8")) or {}
        self.env = load_env(self.path)
        self.defaults = load_defaults()

    # Convenience accessors -------------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.profile
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def save_profile(self) -> None:
        self.profile_path.write_text(dump_yaml(self.profile), encoding="utf-8")

    @property
    def tracker_path(self) -> Path:
        return self.path / self.get("tracker.xlsx_path", "tracker/Job_Search_Tracker.xlsx")

    @property
    def country(self) -> Dict[str, Any]:
        code = self.get("search.country", "de")
        return self.defaults["countries"].get(code, {"name": code, "language": None, "location_keywords": []})


def dump_yaml(data: Dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110)


def open_workspace(explicit: Optional[str] = None) -> Workspace:
    return Workspace(find_workspace(explicit))
