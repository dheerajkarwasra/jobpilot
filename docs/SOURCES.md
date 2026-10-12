# Job sources

| Source | Countries | Cost | Setup |
|---|---|---|---|
| Arbeitnow | DE, AT, CH | free | none |
| Bundesagentur fuer Arbeit | DE | free | none |
| Company watchlist (Greenhouse, Lever, Ashby, Personio, Recruitee, SmartRecruiters, Workday) | any | free | add companies |
| Adzuna | DE, AT, CH, NL, FR, UK, US, IN and more | free key | developer.adzuna.com |
| LinkedIn via Apify | any | Apify credits | Apify token |
| Xing via Apify | DE, AT, CH | Apify credits | Apify token |

Each source runs on its own. If one fails, the others still run and the failure is noted in the Run Log.

## Company watchlist

The most reliable source. Many companies publish their openings through a public job board API, so JobPilot reads them directly without scraping.

```bash
jobpilot watchlist add "DeepL"              # tries the known ATS providers for you
jobpilot watchlist add "Acme" --ats greenhouse --slug acme --why "AI team in Berlin"
jobpilot watchlist list
jobpilot watchlist remove "Acme"
```

To find the slug by hand, open the company's job page and look at the URL, for example `boards.greenhouse.io/acme` or `jobs.lever.co/acme`.

Workday needs a two part slug because large companies host their boards per tenant and site. The career URL looks like `https://sap.wd3.myworkdayjobs.com/SAPCareers/...`, which gives:

```bash
jobpilot watchlist add "SAP" --ats "workday:sap.wd3/SAPCareers"
```

Leave out the `.wd3` part and JobPilot tries wd1, wd3, wd5 and wd2. Workday lists have no description, so details are fetched for recent postings only (capped at 25 per company per run).

Watchlist companies get a small score bonus.

## Adzuna

Sign up at developer.adzuna.com, create an app and copy the app id and key into setup. The free tier is enough for a few runs a day.

## LinkedIn and Xing through Apify

LinkedIn, Xing, StepStone and Indeed block direct automated access. Apify runs community scrapers for you and charges per result.

- Free Apify accounts get about 5 USD of credits per month
- JobPilot keeps a monthly budget (default 4 USD) and stops calling Apify when it is spent
- Apify runs only at the hours in `sources.apify_run_hours` (default 06 and 18), so a 6 hourly schedule calls it twice a day
- Spending per run is written to the Run Log

Settings in `profile.yaml` under `sources`:

```yaml
apify_monthly_budget_usd: 4.0
apify_run_hours: [6, 18]
apify_linkedin_queries: ["Working Student Software Engineer", "Werkstudent Python"]
apify_linkedin_per_query: 30
apify_xing_per_query: 40
```

Scraping is against the terms of some sites. You decide whether to turn it on.

## Sources you add by hand

Found something on StepStone, Indeed, a university board or a meetup? Add it:

```bash
jobpilot add --company "Acme" --title "Working Student Backend" --link https://... --description "paste the text"
```

It goes through the same scoring and dedupe.

## Adding a new source

Write a module in `src/jobpilot/sources/` with a `fetch(ctx) -> List[Job]` function, register it in `sources/__init__.py`, add a switch in `search.enabled_sources` and a fixture based test. See CONTRIBUTING.md.
