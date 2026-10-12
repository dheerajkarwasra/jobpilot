---
name: jobpilot-apply
description: "Prepare a job application for {{name}}: assess chances and fit like a senior hiring manager, then write a tailored cover letter, resume and recruiter message. Use when the user shares a job link, pasted job description or a tracker ID like J0012, or asks for a cover letter, tailored resume or message to a recruiter."
argument-hint: "[job ID, link or pasted description]"
---

# Prepare an application

Job to work on: {{args}}

Follow the workspace instructions file (CLAUDE.md, AGENTS.md or GEMINI.md) for the full rules. This is the short version.

1. **Get the posting.**
   - Tracker ID (like J0012): run `{{cli}} show <ID>`, then fetch the link for the full description.
   - Link: fetch it. If the page is blocked, ask the user to paste the text.
   - Save the description to `job-descriptions/<company>-<role>.md`. If the job is not in the tracker yet, run `{{cli}} add --company "<company>" --title "<title>" --link "<url>"` and note the new ID.
2. **Read** `resume/resume.md` and `profile.yaml`.
3. **Ask once** which documents they want (cover letter, tailored resume, recruiter or hiring team message) and the format (DOCX, PDF, plain text). Skip this if they already said.
4. **Assessment, always:**
   - Chances: a percentage range of getting an interview, with one line on why.
   - Fit table: requirement, match (yes / partly / no), evidence from the resume.
   - Resume changes: concrete line edits for this role.
   - Red flags: {{red_flags}}
   - Verdict: apply, apply with changes, or skip, with the reason.
   Write this as a blunt senior hiring manager at that kind of company. Name what would get the resume rejected in 30 seconds.
5. **Write the documents** into `applications/<company-slug>/`:
   - `<company>-<role>-cover-letter.md`
   - `<company>-<role>-resume.md`, a full tailored resume, not a diff
   - `<company>-<role>-message.md`
   Then export: `{{cli}} export <file>.md --format docx` (or `pdf`).
6. **Writing rules:** {{writing_rules_inline}} Never invent facts or numbers. Ask when a number is missing.
7. **Finish** with the file paths and one line on what to do next. When the user confirms they applied, run `{{cli}} track <ID> Applied --note "<channel>, <documents>"`.
