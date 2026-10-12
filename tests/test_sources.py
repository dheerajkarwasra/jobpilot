from jobpilot.sources import SearchContext, adzuna, apify, arbeitnow, ats, bundesagentur
from jobpilot.sources.base import strip_html, to_date

from conftest import FakeHttp, load


def ctx(ws, routes, hour=6):
    return SearchContext(ws=ws, http=FakeHttp(routes), today="2026-10-12",
                         queries_en=["Working Student Software Engineer"], queries_local=["Werkstudent Softwareentwicklung"],
                         max_age_days=3, run_hour=hour)


def test_helpers():
    assert strip_html("&lt;p&gt;Hello &amp;amp; bye&lt;/p&gt;") == "Hello & bye"
    assert to_date(1791700000) == "2026-10-11"
    assert to_date(1791700000000) == "2026-10-11"
    assert to_date("2026-10-10T10:00:00-04:00") == "2026-10-10"
    assert to_date("") == ""


def test_arbeitnow(workspace):
    jobs = arbeitnow.fetch(ctx(workspace, {"arbeitnow.com": load("arbeitnow.json")}))
    assert len(jobs) == 6
    j = jobs[0]
    assert j.company == "Glindway GmbH" and j.source == "Arbeitnow"
    assert j.posting_ref == "AN-123456" and j.posted_date == "2026-10-11"
    assert "LLM agents" in j.description and "<p>" not in j.description


def test_bundesagentur(workspace):
    jobs = bundesagentur.fetch(ctx(workspace, {"arbeitsagentur.de": load("bundesagentur.json")}))
    assert jobs and jobs[0].posting_ref == "BA-10001-1234567-S"
    assert jobs[0].link.endswith("10001-1234567-S")


def test_adzuna_needs_key(workspace):
    import pytest
    from jobpilot.sources.base import SourceError
    with pytest.raises(SourceError):
        adzuna.fetch(ctx(workspace, {}))
    workspace.env.update({"JOBPILOT_ADZUNA_APP_ID": "x", "JOBPILOT_ADZUNA_APP_KEY": "y"})
    jobs = adzuna.fetch(ctx(workspace, {"adzuna.com": load("adzuna.json")}))
    assert jobs[0].title == "Junior Backend Developer" and jobs[0].posting_ref == "AZ-5555"


def test_ats_parsers(workspace):
    h = FakeHttp({"greenhouse.io": load("greenhouse.json"), "lever.co": load("lever.json"),
                  "ashbyhq.com": load("ashby.json"), "personio.de": load("personio.xml")})
    gh = ats._greenhouse(h, "acmeai", "Acme AI")
    assert len(gh) == 3 and gh[0].posting_ref == "REQ-2026-77" and "RAG" in gh[0].description
    lv = ats._lever(h, "acme", "Acme")
    assert lv[0].posted_date == "2026-10-11" and lv[0].employment_hint == "Internship"
    ab = ats._ashby(h, "acme", "Acme")
    assert ab[0].remote_hint is True
    pe = ats._personio(h, "acme", "Acme")
    assert pe[0].posting_ref == "PE-4242" and "Python" in pe[0].description


def test_probe_finds_first_working_ats():
    h = FakeHttp({"api.ashbyhq.com/posting-api/job-board/deepl": load("ashby.json")})
    assert ats.probe(h, "DeepL SE") == ("ashby", "deepl", 1)
    assert ats.probe(FakeHttp({}), "Nobody GmbH") is None
    assert ats.slug_candidates("Rohde & Schwarz GmbH") == ["rohdeschwarz", "rohde-schwarz", "rohde"]


def test_apify_budget_and_hours(workspace):
    workspace.env["JOBPILOT_APIFY_TOKEN"] = "t"
    c = ctx(workspace, {"apify.com": load("linkedin.json")}, hour=6)
    jobs = apify.fetch_linkedin(c)
    assert jobs and jobs[0].posting_ref == "LI-4476180019"
    assert jobs[0].link == "https://www.linkedin.com/jobs/view/4476180019"
    assert c.apify_spent_this_run > 0
    # wrong hour: skipped
    c2 = ctx(workspace, {"apify.com": load("linkedin.json")}, hour=12)
    assert apify.fetch_linkedin(c2) == [] and "skipped" in c2.log[0]
    # over budget: skipped
    c3 = ctx(workspace, {"apify.com": load("linkedin.json")}, hour=6)
    c3.apify_spent_this_month = 3.99
    assert apify.fetch_linkedin(c3) == []
