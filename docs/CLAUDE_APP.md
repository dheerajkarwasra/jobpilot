# Running it in the Claude app with connectors

If you use the Claude app, you can run the whole search in the cloud instead of on your laptop:

- the tracker lives in Google Sheets through the Sheets connector
- replies are read through the Gmail connector (read only)
- the search and inbox check run as scheduled tasks, even when your laptop is off

Pick "Claude app" as an assistant in `jobpilot setup` (or run `jobpilot assistants --targets claude_app`). JobPilot writes `exports/CLAUDE_APP_SETUP.md` in your workspace. It is a step by step guide with:

1. Which connectors to turn on
2. How to create the Project and paste your instructions
3. A ready prompt that creates the tracker sheet with the right tabs and columns
4. A scheduled task prompt for the job search, filled in with your queries, filters, languages and scoring
5. A scheduled task prompt for the daily read only Gmail check

The prompts are generated from your `profile.yaml`, so they match the local setup. Run `jobpilot assistants` after changing your profile to regenerate them.

## Local or cloud?

| | Local (`jobpilot` CLI) | Claude app |
|---|---|---|
| Runs when laptop is off | no | yes |
| Tracker | Excel or Google Sheets | Google Sheets |
| Mail access | IMAP app password | Gmail connector |
| Search quality | fixed pipeline, same result every run | model follows the prompt, can also use web search |
| Cost | free (plus optional Apify) | uses your Claude plan |
| Works with Codex and Gemini | yes | no |

You can use both. Point the local tracker at the same Google Sheet (docs/GOOGLE_SHEETS.md) and the dedupe keeps it clean.

What JobPilot can not do for you: connectors and scheduled tasks belong to your Claude account, so you create them yourself in the app by following the guide. Nothing from one person's account is shared with anyone else.
