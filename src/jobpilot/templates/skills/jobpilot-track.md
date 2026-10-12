---
name: jobpilot-track
description: "Update and report on {{name}}'s job applications in the JobPilot tracker. Marks jobs applied, rejected or interviewing, adds jobs found elsewhere, checks email replies, drafts follow-ups and summarises the pipeline. Use when the user says they applied somewhere, got a reply, wants a status update, or asks what to follow up on."
argument-hint: "[e.g. 'applied to J0012 via LinkedIn' or 'status']"
---

# Track applications

Request: {{args}}

- Status overview: run `{{cli}} status` and summarise in at most 8 lines. List actions first (interviews to schedule, tests due, follow-ups), then counts.
- The user applied: `{{cli}} track <ID> Applied --note "<channel>, <documents sent>"`. If the job is not tracked yet, run `{{cli}} add --company ... --title ... --link ... --status Applied` first.
- A reply came in: set the matching status (Screening, Interview, Offer, Rejected) with `{{cli}} track <ID> <Status> --note "<one line summary>"`.
- Check mail now: `{{cli}} inbox` (needs inbox setup). Report actions first.
- Follow-ups: for applications older than 14 days with no reply, draft a short polite follow-up (under 90 words, quote the Posting Ref) and save it to `applications/<company>/<company>-follow-up.md`. Never send mail yourself.
- Interview prep: when a job reaches Interview, offer a prep sheet: likely questions for that company type, three stories from the resume that fit, and questions to ask them. Save it to `applications/<company>/interview-prep.md`.
- Write in plain language: {{writing_rules_inline}}
