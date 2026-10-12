---
name: jobpilot-search
description: "Find and triage new job postings for {{name}}. Runs the JobPilot search across free job boards, the company watchlist and optional paid sources, then ranks what is worth applying to. Use when the user asks for new jobs, what to apply to next, or to check the review queue."
argument-hint: "[optional: extra keywords or 'queue' to only review]"
---

# Search and triage

Request: {{args}}

1. Unless the request is only about the queue, run `{{cli}} search`. If it reports failed sources, mention them in one line at the end.
2. Run `{{cli}} status` to see the review queue (Status = Found, best fit first).
3. For the top High fit postings (up to 8): fetch the link, read the description, and give each one a one line verdict:
   - `J0042 Company, Title: apply / maybe / skip, because <reason>`
   - Flag language requirements the detector missed (for example "fluent {{local_language}}" in the text). If a posting needs a language level the user does not have, run `{{cli}} track <ID> Skipped --note "language"`.
4. Ask which ones to prepare. For each one they pick, follow the jobpilot-apply skill.
5. When the user rejects a posting, run `{{cli}} track <ID> Skipped`. To favour or block companies or keywords, edit `search.exclude_title`, `search.exclude_companies` or `scoring.keywords` in `profile.yaml`, but only after the user agrees.
6. To watch a specific company, run `{{cli}} watchlist add "<Company name>"`. It detects the company's careers system automatically.
