# FAQ and troubleshooting

**`jobpilot: command not found` after installing**
Open a new terminal. If it still fails, add `~/.local/bin` to PATH (macOS, Linux) or `%USERPROFILE%\.jobpilot\bin` (Windows).

**The search finds nothing**
Run `jobpilot search --dry-run` and look at the counts per filter. Usually `max_age_days` is too small, `must_match_any` too narrow, or the local language limit too strict. Add companies to the watchlist for steady results.

**Too many irrelevant jobs**
Add words to `exclude_title`, tighten `must_match_any`, or raise `scoring.weights.high_threshold`.

**A job I care about was dropped for language**
Raise `max_local_language_level_ok`, or add it by hand with `jobpilot add`.

**Bundesagentur fails**
The public API key sometimes changes. The run continues with other sources. Check for an update with the installer.

**LinkedIn shows nothing**
Apify runs only at the hours in `sources.apify_run_hours` (default 6 and 18) to save credits. To test at another time, set `sources.apify_respect_hours: false` in `profile.yaml`, run `jobpilot search --sources apify_linkedin`, then set it back.

**Inbox login fails**
Use an app password, not your normal password. For Gmail, 2 Step Verification must be on. Work Microsoft accounts often block IMAP.

**The Excel file is locked**
Close it in Excel before a scheduled run, or switch to Google Sheets.

**Can I use it without any AI assistant?**
Yes. Search, tracking, inbox and export all work from the command line.

**Does it apply to jobs for me?**
No, never. It finds, tracks and helps you write. You apply yourself.

**Does it work outside Germany?**
Yes, with Adzuna, the watchlist and LinkedIn. The free German sources only run for Germany (and Arbeitnow for Austria and Switzerland).

**How do I start over?**
Delete or rename the workspace folder and run `jobpilot setup`.
