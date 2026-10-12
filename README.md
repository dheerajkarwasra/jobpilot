# JobPilot

[![CI](https://github.com/dheerajkarwasra/jobpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/dheerajkarwasra/jobpilot/actions/workflows/ci.yml)

A job search copilot that runs on your laptop. It finds postings that fit you, keeps them in one tracker, reads replies from your inbox, and plugs into the AI coding assistant you already use (Claude Code, Codex CLI or Gemini CLI) so it can write a tailored cover letter, resume or recruiter message for any job in a few minutes.

It was built for students and early career developers looking for Werkstudent, internship and junior roles in Germany, but every part is configurable: country, role types, fields, languages, scoring, sources and writing style.

## Install

macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/dheerajkarwasra/jobpilot/main/install.sh | bash
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/dheerajkarwasra/jobpilot/main/install.ps1 | iex
```

You need Python 3.9 or newer. The installer puts everything in `~/.jobpilot`, adds a `jobpilot` command and starts the setup wizard. Run it again later to update.

Prefer to do it by hand?

```bash
git clone https://github.com/dheerajkarwasra/jobpilot.git
cd jobpilot
python3 -m venv .venv && source .venv/bin/activate
pip install .            # or: pip install ".[gsheets]" for Google Sheets
jobpilot setup
```

## What setup asks

The wizard takes about five minutes. Press Enter to accept a default. You can re-run `jobpilot setup` any time and it keeps your earlier answers.

1. Where to keep your workspace (default `~/JobPilot`)
2. Your resume (DOCX, PDF, TXT or MD). Name, email, links and skills are read from it and shown for you to confirm
3. Contact details, education, work permit and hours limit
4. Languages you speak, with a level (A1 to C2 or Native)
5. Country, remote, role types (Werkstudent, internship, thesis, entry level, full time) and fields (software, AI, data, DevOps, frontend, security)
6. Search queries, which are generated for you and can be edited
7. The highest local language level a job may ask for and still be shown
8. Title keywords and companies to skip
9. Writing rules and banned words for everything written for you
10. Which assistants you use: Claude Code, Codex CLI, Gemini CLI, a Claude or ChatGPT Project, or the Claude app with connectors and scheduled tasks
11. Tracker: an Excel file (default) or Google Sheets
12. Optional sources: Adzuna (free key) and LinkedIn or Xing through Apify (paid credits, with a monthly cap)
13. Companies to watch directly on their career pages
14. Automatic runs: search every N hours, inbox check once a day

For an unattended setup, pass a YAML file: `jobpilot setup --answers my-answers.yaml`. See [examples/answers.example.yaml](examples/answers.example.yaml).

## Daily use

Open your workspace folder in your assistant and talk to it, or use the commands.

| In Claude Code | In Codex CLI | In Gemini CLI | What it does |
|---|---|---|---|
| `/jobpilot-search` | `$jobpilot-search` | `/jobpilot-search` | Run a search and walk through the best new jobs |
| `/jobpilot-review` | `$jobpilot-review` | `/jobpilot-review` | Go through the review queue, shortlist or skip |
| `/jobpilot-apply J0012` | `$jobpilot-apply J0012` | `/jobpilot-apply J0012` | Assess fit and chances, then write cover letter, resume or message |
| `/jobpilot-track` | `$jobpilot-track` | `/jobpilot-track` | Update statuses, list follow-ups, check the inbox |

You can also paste a job link or description and ask "should I apply?". The assistant follows the rules in `CLAUDE.md`, `AGENTS.md` or `GEMINI.md`, which setup writes for you.

The command line works without any assistant:

```bash
jobpilot search                 # find new jobs now
jobpilot status                 # pipeline and review queue
jobpilot show J0012             # one job
jobpilot track J0012 Applied --note "company site, CV and cover letter"
jobpilot add --company "Acme" --title "Working Student Backend" --link https://...
jobpilot inbox                  # read replies and update statuses (read only)
jobpilot watchlist add "DeepL"  # finds the career page API automatically
jobpilot export applications/acme/acme-backend-cover-letter.md --format pdf
jobpilot schedule install       # run search and inbox automatically
jobpilot doctor                 # check that everything works
```

## How the search works

Every run pulls from free sources first: Arbeitnow (Germany, Austria, Switzerland), the Bundesagentur fuer Arbeit job search (Germany), Adzuna if you add a key, and the public job APIs of companies on your watchlist (Greenhouse, Lever, Ashby, Personio, Recruitee, SmartRecruiters and Workday, which most large employers use). LinkedIn and Xing are optional through Apify and run at most twice a day inside the budget you set.

Each posting then goes through the same pipeline:

- **Role type**: Werkstudent, internship, thesis, entry or full time, from title markers in English and the local language
- **Location**: your country, or remote when you allow it
- **Age**: older than your limit (default 3 days) is dropped
- **Exclusions**: titles and companies you never want
- **Language**: detects the posting language and any required level. Jobs asking for more than you allow are dropped; unclear ones are kept and marked "Likely"
- **Scoring**: points for English, your skills and watchlist companies, minus points for local language risk, full time roles on a student permit, and consultancies. Each job gets High, Medium or Low fit
- **Dedupe**: the same job from two sources, or already in your tracker, is added once, with the other source noted

The full rubric is in your `profile.yaml` and can be changed. See [docs/CUSTOMIZE.md](docs/CUSTOMIZE.md).

## The tracker

One workbook with these tabs:

- **Dashboard**: counts by status, fit and source, follow-ups due, and a short how to
- **Jobs**: every posting with ID, status, fit, score, posting reference, language info and link
- **Review Queue**: new jobs sorted newest and best first
- **Applications**: what you sent, when, to whom, next step and follow-up date
- **Watchlist** and **Run Log**

Statuses: Found, Shortlisted, Applied, Screening, Interview, Offer, Rejected, Ghosted, Withdrawn, Skipped. A status never moves backwards unless you pass `--force`.

## Privacy

Everything stays on your computer. Your profile, resume, tracker and documents live in your workspace folder. Secrets (API keys, the mail app password) live in `.env` in that folder with owner only permissions, and the workspace has a `.gitignore` that keeps all of it out of git. The inbox check is strictly read only: it never sends, replies, moves, labels or deletes mail. See [docs/PRIVACY.md](docs/PRIVACY.md).

## Docs

- [Setup in detail](docs/SETUP.md)
- [Using it with Claude Code, Codex, Gemini or a Project](docs/ASSISTANTS.md)
- [Running it in the Claude app with Google Sheets, Gmail and scheduled tasks](docs/CLAUDE_APP.md)
- [Job sources and costs](docs/SOURCES.md)
- [Google Sheets tracker](docs/GOOGLE_SHEETS.md)
- [Inbox check and app passwords](docs/INBOX.md)
- [Automatic runs](docs/SCHEDULING.md)
- [Customizing everything](docs/CUSTOMIZE.md)
- [Privacy and security](docs/PRIVACY.md)
- [FAQ and troubleshooting](docs/FAQ.md)

## Development

```bash
pip install -e ".[dev,gsheets]"
pytest
```

Tests run offline against recorded fixtures. Pull requests for new sources, countries or assistant targets are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. Job data belongs to the sites it comes from. Respect each site's terms and use the optional scrapers at your own risk.
