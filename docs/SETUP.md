# Setup in detail

## 1. Install

Use the one line installer from the README, or install by hand:

```bash
git clone https://github.com/dheerajkarwasra/jobpilot.git && cd jobpilot
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install .
```

Add Google Sheets support with `pip install ".[gsheets]"` (or `JOBPILOT_EXTRAS=gsheets` before the installer).

## 2. Run the wizard

```bash
jobpilot setup
```

Have these ready:

- Your resume as DOCX, PDF, TXT or Markdown
- Your language levels (A1 to C2 or Native)
- Optional: an Adzuna app id and key, an Apify token, a mail app password

The wizard reads your resume and prefills name, email, phone, links and skills. Check them, it guesses.

## 3. What it creates

```
~/JobPilot/
  profile.yaml          your settings, edit freely
  .env                  secrets, owner only permissions, never commit
  .gitignore
  resume/               your original resume and resume.md (plain text the assistant reads)
  tracker/              Job_Search_Tracker.xlsx
  job-descriptions/     saved postings
  applications/         one folder per company with generated documents
  exports/              PROJECT_INSTRUCTIONS.md if you chose a Project
  logs/                 output of automatic runs
  CLAUDE.md / AGENTS.md / GEMINI.md and skill folders for the assistants you picked
```

The workspace location is remembered in `~/.config/jobpilot/workspace`, so `jobpilot` works from any folder. Override it with `--workspace PATH` or the `JOBPILOT_HOME` variable.

## 4. First search

At the end the wizard offers a first search. Run it again any time with `jobpilot search`. Use `jobpilot search --dry-run` to see what would be added without writing.

## 5. Check everything

```bash
jobpilot doctor
```

## Re-running setup

`jobpilot setup` is safe to re-run. Every question defaults to your current answer, secrets you leave empty stay as they are, and settings you added by hand in `profile.yaml` are kept.

## Unattended setup

Write your answers in YAML and pass them in. Any question you leave out takes its default. See `examples/answers.example.yaml`.

```bash
jobpilot setup --answers answers.yaml --no-search
```

Do not commit an answers file that holds secrets.

## Updating

Run the installer again. For a manual install: `git pull && pip install .` in the repo. After an update, run `jobpilot assistants` to refresh the assistant files with the latest templates.

## Uninstalling

```bash
jobpilot schedule remove
rm -rf ~/.jobpilot ~/.local/bin/jobpilot ~/.config/jobpilot
```

Your workspace (`~/JobPilot`) is yours to keep or delete.
