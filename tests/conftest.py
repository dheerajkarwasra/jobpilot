import json
from pathlib import Path

import pytest
import yaml

from jobpilot import config
from jobpilot.sources.base import SourceError

FIX = Path(__file__).parent / "fixtures"


class FakeHttp:
    """Routes URLs to fixture payloads by substring."""

    def __init__(self, routes=None):
        self.routes = routes or {}
        self.calls = []

    def _find(self, url):
        self.calls.append(url)
        for key, val in self.routes.items():
            if key in url:
                if isinstance(val, Exception):
                    raise val
                return val
        raise SourceError(f"404 Not Found: {url}")

    def get_json(self, url, params=None, headers=None):
        return self._find(url)

    def get_text(self, url, params=None, headers=None):
        return self._find(url)

    def post_json(self, url, payload, params=None, timeout=300):
        return self._find(url)


def load(name):
    p = FIX / name
    return json.loads(p.read_text()) if p.suffix == ".json" else p.read_text()


BASE_ANSWERS = {
    "name": "Alex Example",
    "email": "alex@example.com",
    "location": "Berlin, Germany",
    "degree": "M.Sc. Computer Science",
    "school": "Example University",
    "graduation": "2027",
    "work_permit": "Student visa, max 20h/week",
    "hours_per_week": "20",
    "languages": [{"language": "English", "level": "C1"}, {"language": "German", "level": "A1"}],
    "country": "de",
    "role_types": ["werkstudent", "internship", "entry"],
    "fields": ["ai", "software"],
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "LangGraph"],
    "assistants": ["claude", "codex", "gemini", "claude_app"],
    "tracker_backend": "xlsx",
    "adzuna": False,
    "apify": False,
    "watchlist": [],
    "probe_watchlist": False,
    "schedule": False,
    "inbox": False,
}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "POINTER_FILE", tmp_path / "cfg" / "workspace")
    resume = tmp_path / "resume.md"
    resume.write_text((FIX / "resume.md").read_text())
    answers = dict(BASE_ANSWERS, workspace=str(tmp_path / "ws"), resume_path=str(resume))
    af = tmp_path / "answers.yaml"
    af.write_text(yaml.safe_dump(answers))
    from jobpilot.wizard import run
    run(answers_file=str(af), skip_search=True)
    ws = config.Workspace(tmp_path / "ws")
    # watchlist entry with known ATS for source tests
    ws.profile["watchlist"] = [{"name": "Acme AI", "active": True, "ats": "greenhouse", "slug": "acmeai", "why": "test"}]
    ws.save_profile()
    return config.Workspace(tmp_path / "ws")
