import re
import sys

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib

import yaml

from jobpilot import adapters
from jobpilot.documents import guess_basics, to_docx, to_pdf


def _frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "missing frontmatter"
    return yaml.safe_load(m.group(1))


def test_profile_built_from_answers(workspace):
    p = workspace.profile
    assert p["person"]["name"] == "Alex Example"
    assert p["search"]["local_language"] == "german"
    assert any(q.startswith("Working Student") for q in p["search"]["queries_en"])
    assert any(q.startswith("Werkstudent") for q in p["search"]["queries_local"])
    assert p["scoring"]["penalize_fulltime"] is True
    assert (workspace.path / "resume" / "resume.md").read_text().startswith("ALEX EXAMPLE")
    assert workspace.tracker_path.exists()
    if sys.platform != "win32":  # Windows has no POSIX file modes
        assert oct((workspace.path / ".env").stat().st_mode)[-3:] == "600"


def test_skills_are_valid_for_every_assistant(workspace):
    ws = workspace.path
    for base in (".claude/skills", ".agents/skills"):
        for name in adapters.SKILLS:
            text = (ws / base / name / "SKILL.md").read_text()
            fm = _frontmatter(text)
            assert fm["name"] == name
            assert 20 < len(fm["description"]) <= 1024
            assert "Alex Example" in fm["description"]
            if base == ".agents/skills":
                assert set(fm) == {"name", "description"}, "Codex and Gemini get only standard keys"
                assert "$ARGUMENTS" not in text
            else:
                assert "$ARGUMENTS" in text
            leftovers = set(re.findall(r"\{\{(\w+)\}\}", text))
            assert not leftovers, f"{base}/{name} unrendered: {leftovers}"


def test_gemini_commands_and_context_files(workspace):
    ws = workspace.path
    for name in adapters.SKILLS:
        data = tomllib.loads((ws / ".gemini" / "commands" / f"{name}.toml").read_text())
        assert data["description"] and "{{args}}" in data["prompt"]
    for f in ("CLAUDE.md", "AGENTS.md", "GEMINI.md"):
        text = (ws / f).read_text()
        assert "Alex Example" in text and "jobpilot" in text
        assert not re.findall(r"\{\{(\w+)\}\}", text)
    assert "$jobpilot-apply" in (ws / "AGENTS.md").read_text()
    proj = (ws / "exports" / "PROJECT_INSTRUCTIONS.md").read_text()
    assert "not available" not in proj and "jobpilot status" not in proj and "## Tracking" in proj


def test_claude_app_guide(workspace):
    from jobpilot import adapters
    adapters.install(workspace, ["claude_app"])
    text = (workspace.path / "exports" / "CLAUDE_APP_SETUP.md").read_text()
    assert not re.findall(r"\{\{(\w+)\}\}", text)
    assert "Alex Example" in text and "Working Student" in text and "Posting Ref" in text
    assert "READ ONLY" in text and "Arbeitnow" in text and "Acme AI (greenhouse: acmeai)" in text
    assert (workspace.path / "exports" / "PROJECT_INSTRUCTIONS.md").exists(), "claude_app implies the project export"


def test_no_em_dashes_in_generated_files(workspace):
    for path in workspace.path.rglob("*.md"):
        assert "—" not in path.read_text(), path


def test_guess_basics_and_export(tmp_path):
    text = "JANE DOE\njane@doe.dev | +49 151 2345678 | linkedin.com/in/janedoe\nPython, FastAPI, Docker and AWS"
    b = guess_basics(text)
    assert b["name"] == "Jane Doe" and b["email"] == "jane@doe.dev" and "FastAPI" in b["skills"]
    md = tmp_path / "letter.md"
    md.write_text("# Cover letter\n\nDear team,\n\nI build **backend** systems in *Python*. Zürich, München.\n\n- one\n- two\n")
    d = to_docx(md, tmp_path / "letter.docx")
    p = to_pdf(md, tmp_path / "letter.pdf")
    assert d.stat().st_size > 1000 and p.read_bytes()[:4] == b"%PDF"
    import docx
    assert "backend" in "\n".join(par.text for par in docx.Document(str(d)).paragraphs)


def test_rerunning_setup_keeps_answers(workspace, tmp_path, monkeypatch):
    from jobpilot import config
    from jobpilot.wizard import run
    answers = {"workspace": str(workspace.path), "schedule": False, "inbox": False, "probe_watchlist": False,
               "assistants": ["claude"]}
    pf = workspace.path / "profile.yaml"
    prof = yaml.safe_load(pf.read_text())
    prof["search"]["include_senior"] = True
    prof["sources"]["arbeitnow_pages"] = 2
    pf.write_text(yaml.safe_dump(prof))
    af = tmp_path / "a2.yaml"
    af.write_text(yaml.safe_dump(answers))
    run(answers_file=str(af), skip_search=True)
    ws2 = config.Workspace(workspace.path)
    assert ws2.profile["person"]["name"] == "Alex Example"
    assert ws2.profile["languages"][1]["language"] == "German"
    assert ws2.profile["search"]["include_senior"] is True, "hand edits survive a re-run"
    assert ws2.profile["sources"]["arbeitnow_pages"] == 2
    assert ws2.profile["skills"][0] == "Python"
