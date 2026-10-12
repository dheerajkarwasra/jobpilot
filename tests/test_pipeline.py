from jobpilot.models import Job
from jobpilot.pipeline import Pipeline, canonical_link, dedupe_key, norm_company, norm_title
from jobpilot.sources import arbeitnow, ats

from conftest import FakeHttp, load
from test_sources import ctx


def test_normalisation():
    assert norm_company("Beispiel GmbH & Co. KG") == norm_company("beispiel")
    assert norm_title("Werkstudent Backend (m/w/d)") == norm_title("Werkstudent Backend (w/m/d)")
    assert norm_title("Working Student AI (all genders)") == norm_title("Working Student AI")
    assert canonical_link("https://de.linkedin.com/jobs/view/foo-bar-at-x-4476180019?position=2") == "linkedin:4476180019"
    assert canonical_link("https://www.linkedin.com/jobs/view/4476180019") == "linkedin:4476180019"


def test_filters_and_scoring(workspace):
    p = Pipeline(workspace, today="2026-10-12")
    jobs = arbeitnow.fetch(ctx(workspace, {"arbeitnow.com": load("arbeitnow.json")}))
    kept, stats = p.process(jobs, set(), set(), set())
    titles = {j.title: j for j in kept}
    # English AI working student: kept, High
    ai = titles["Working Student AI Software Engineer (m/f/d)"]
    assert ai.fit == "High" and ai.type == "Werkstudent" and ai.language_required in ("No", "Optional")
    # German C1 required: dropped
    assert "Werkstudent Backend Entwicklung (m/w/d)" not in titles and stats["language"] == 1
    # Controlling: excluded by title. Senior role: not a target type. Old posting: too old.
    assert stats["excluded"] == 1 and stats["type"] == 1 and stats["old"] == 1
    # German posting without a stated level: kept but Likely, with a penalty
    de = titles["Werkstudent Softwareentwicklung (m/w/d)"]
    assert de.posting_language == "DE" and de.language_required == "Likely" and de.fit != "High"


def test_location_filter(workspace):
    p = Pipeline(workspace, today="2026-10-12")
    h = FakeHttp({"greenhouse.io": load("greenhouse.json")})
    jobs = ats._greenhouse(h, "acmeai", "Acme AI")
    kept, stats = p.process(jobs, set(), set(), set())
    # Munich kept, US sales and London intern dropped (location / title)
    assert [j.title for j in kept] == ["Working Student Machine Learning (f/m/d)"]
    assert kept[0].language_required == "Optional"
    assert "watchlist" in kept[0].notes


def test_dedupe_against_tracker_and_within_run(workspace):
    p = Pipeline(workspace, today="2026-10-12")
    a = Job(title="Working Student AI Engineer (m/w/d)", company="Foo GmbH", link="https://a.example/1", source="Arbeitnow",
            location="Berlin", description="Python LLM agents, English team", posted_date="2026-10-11")
    b = Job(title="Working Student AI Engineer (f/m/d)", company="Foo", link="https://b.example/2", source="LinkedIn",
            location="Berlin", description="Python LLM agents, English team. Longer description here.", posted_date="2026-10-11",
            posting_ref="LI-1")
    kept, stats = p.process([a, b], set(), set(), set())
    assert len(kept) == 1 and stats["duplicate"] == 1 and "also on" in kept[0].notes
    kept2, stats2 = p.process([a], set(), set(), {dedupe_key(a)})
    assert kept2 == [] and stats2["duplicate"] == 1


def test_user_with_b2_german_is_not_filtered(workspace):
    workspace.profile["languages"] = [{"language": "German", "level": "C1"}]
    p = Pipeline(workspace, today="2026-10-12")
    jobs = arbeitnow.fetch(ctx(workspace, {"arbeitnow.com": load("arbeitnow.json")}))
    kept, stats = p.process(jobs, set(), set(), set())
    assert stats["language"] == 0
    assert any(j.title.startswith("Werkstudent Backend") for j in kept)
