# Customizing JobPilot

Everything personal lives in `profile.yaml` in your workspace. Edit it, then run:

```bash
jobpilot assistants     # refresh CLAUDE.md, AGENTS.md, GEMINI.md, skills and exports
jobpilot doctor
```

Re-running `jobpilot setup` keeps your hand edits.

## Search

```yaml
search:
  country: de                       # de, at, ch, nl, fr, uk, us, in
  remote_ok: true
  role_types: [werkstudent, internship, entry]     # also: thesis, fulltime
  fields: [ai, software]            # also: data, devops, frontend, security
  queries_en: ["Working Student Backend Developer", "Junior Python Developer"]
  queries_local: ["Werkstudent Softwareentwicklung"]
  max_age_days: 3                   # drop older postings
  max_local_language_level_ok: A2   # drop jobs asking for more than this
  must_match_any: [python, backend, api]           # a job needs at least one
  exclude_title: [sales, marketing]
  exclude_description: []
  exclude_companies: [Randstad, Hays]
  location_keywords: [germany, deutschland, berlin]
  include_senior: false             # true keeps senior roles as Full time
```

## Scoring

```yaml
scoring:
  keywords:
    primary: [llm, agent, rag]      # +3 if any match
    core: [python, fastapi]         # +2 if any match
    secondary: [docker, sql]        # +1 if any match
  penalize_fulltime: true
  weights:                          # override any default weight
    english_or_language_ok: 3
    primary_keyword: 3
    core_keyword: 2
    secondary_keyword: 1
    watchlist_company: 1
    language_likely_needed: -2
    fulltime_visa_risk: -2
    consultancy: -1
    high_threshold: 6
    medium_threshold: 3
```

The full default list is in `src/jobpilot/data/defaults.yaml`.

## Writing style

```yaml
writing:
  rules:
    - Plain, human sounding language
    - No em dashes
  banned_words: [passionate, synergy, leverage]
  cover_letter_paragraphs: 3 to 4
```

## Sources

```yaml
sources:
  arbeitnow: true
  bundesagentur: true
  adzuna: false
  watchlist: true
  apify_linkedin: false
  apify_xing: false
  apify_monthly_budget_usd: 4.0
  apify_run_hours: [6, 18]
  arbeitnow_pages: 5
```

## Adding a country

Add an entry under `countries` in `defaults.yaml` with its name, language, location keywords and Adzuna code. If the language is new, add it under `languages` with stopwords and phrases for "required" and "optional". Send a pull request so others get it too.

## Changing what the assistant does

The assistant files are generated from templates in `src/jobpilot/templates/`:

- `instructions.md` becomes CLAUDE.md, AGENTS.md, GEMINI.md and the Project export
- `skills/*.md` become the slash commands and skills
- `claude_app.md` becomes the Claude app guide

Edit a template, reinstall (`pip install .`) and run `jobpilot assistants`. To keep a personal change without touching the package, edit the generated file in your workspace, but note that `jobpilot assistants` overwrites it.
