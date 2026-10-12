# Run JobPilot inside the Claude app (connectors and scheduled tasks)

This guide sets up the same job search for {{name}} inside the Claude app instead of on this computer. Claude keeps the tracker in Google Sheets, reads replies from Gmail and runs on a schedule in the cloud, so it works even when the laptop is off.

You can use this instead of the local setup or next to it. If you use both, point them at the same Google Sheet (see docs/GOOGLE_SHEETS.md) so jobs are not added twice.

## 1. Connect your apps

In the Claude app, open Settings > Connectors and connect:

- **Google Drive** and **Google Sheets** (the tracker)
- **Gmail** (the daily reply check, read only)
- Optional: **Indeed** if it is offered to you, and **Apify** for LinkedIn and Xing

Use the Google account you apply with.

## 2. Create a Project

Create a Project named "Job applications". Paste `exports/PROJECT_INSTRUCTIONS.md` into its instructions and upload your resume. Every chat in the Project now follows your workflow and writing rules.

## 3. Create the tracker sheet

In a chat inside the Project, send:

```
Create a Google Sheet named "Job Search Tracker" with these tabs and header rows, freeze the header row, and give me the link:
- Jobs: {{job_columns}}
- Applications: {{application_columns}}
- Run Log: {{runlog_columns}}
- Watchlist: {{watchlist_columns}}
Add a Status dropdown in Jobs and Applications with: {{statuses}}.
```

Copy the sheet ID from the link (the part between `/d/` and `/edit`) and replace `SHEET_ID` in the two prompts below.

## 4. Scheduled task: job search

Ask Claude to "create a scheduled task" that runs every {{every_hours}} hours, with this prompt:

```
Job search for {{name}}. Tracker: Google Sheet SHEET_ID.

Profile: {{targets}} in {{country}}{{remote_text}}. Languages: {{languages}}. Skills: {{skills}}.

1. Read the Jobs tab. Collect existing links, Posting Refs and company + title pairs so you never add a duplicate. Note the highest ID (J0001 style).
2. Search for postings from the last {{max_age}} days with these queries:
   English: {{queries_en}}
   {{local_language}}: {{queries_local}}
   Sources, free first:
   {{source_lines}}
   - Web search for each query plus site names (LinkedIn, StepStone, Indeed, Xing, Glassdoor, company career pages) to find more links
3. Keep a job only if:
   - it is one of: {{targets}}
   - it is in {{country}}{{remote_text}}
   - the title does not contain: {{exclude_title}}
   - the company is not: {{exclude_companies}}
   - it does not require {{local_language}} above {{max_level}}
4. Score it: +3 English posting or {{local_language}} optional, +3 if it mentions any of {{primary_keywords}}, +2 if any of {{core_keywords}}, +1 per other matching skill, +1 watchlist company, -2 if {{local_language}} is likely required, -2 full time{{fulltime_note}}, -1 consultancy. Fit is High at 6 or more, Medium at 3 or more, else Low.
5. Append each new job to Jobs with Status Found, the posting's own reference number in Posting Ref if it has one, today's date in Date Found, and the direct link.
6. Add one row to Run Log ({{runlog_columns}}) with Task "Job search".
7. Reply with the new High fit jobs as a short list: ID, company, title, link. If nothing new, say so in one line.

Never apply to anything, never email anyone, never edit rows you did not add.
```

## 5. Scheduled task: inbox check

Create a second scheduled task, once a day at {{inbox_time}}, with this prompt:

```
Daily application inbox check for {{name}}. Tracker: Google Sheet SHEET_ID.

Gmail is READ ONLY in this task. Never send, reply, draft, forward, label, archive, mark read or delete anything.

1. Search Gmail for the last 2 days: replies about job applications in English or German (application received, Eingangsbestaetigung, coding test, interview, Vorstellungsgespraech, offer, Absage, unfortunately, leider). Ignore job alert newsletters.
2. Match each mail to a row in Jobs by company name, sender domain, job title or Posting Ref. Skip weak matches.
3. Classify it as Applied, Screening, Interview, Offer or Rejected. Move the status forward only, never backward (order: {{statuses}}).
4. Update the job row and the matching Applications row: Status, Last Response Date, Next Step, and a dated note like "YYYY-MM-DD: interview mail from recruiter". Put the Gmail message id in Mail Reference.
5. For Applications with Status Applied and no reply: after 21 days set Next Step to "Send polite follow-up", after 35 days set Status to Ghosted.
6. Add one row to Run Log with Task "Inbox check".
7. Reply with what changed and the follow-ups due. If nothing changed, one line.
```

## 6. Day to day

In the Project, paste a job link or a tracker ID and say what you need. Claude gives your chances, fit, resume changes and red flags, then writes the documents. Say "mark J0012 applied" to update the sheet.

Re-run `jobpilot assistants` after editing `profile.yaml` to regenerate this guide with your new settings.
