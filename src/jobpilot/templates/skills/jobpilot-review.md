---
name: jobpilot-review
description: "Review {{name}}'s resume the way a blunt senior hiring manager would, either in general for their target roles or against one specific job. Use when the user asks to review, critique, score or improve their resume or LinkedIn profile."
argument-hint: "[optional job ID, link or role type]"
---

# Resume review

Target: {{args}} (if empty, review against the target roles in profile.yaml: {{targets}})

1. Read `resume/resume.md` and `profile.yaml`. If a job ID or link is given, get the description first (`{{cli}} show <ID>` or fetch the link).
2. Decide which kind of company you are reviewing for (top tier tech, scale up, startup, traditional company, consultancy) and take that hiring manager's view.
3. Give, in this order:
   - **Score out of 10** and one line on why.
   - **Rejected in 30 seconds because...**: the top 3 to 5 problems a screener would see first (layout, handle names, unexplained gaps, unclear dates, vague claims, missing location or language info).
   - **Market fit**: a table of what is strong and what is missing for {{targets}} in {{country}}.
   - **Line by line edits**: quote the current line, then give the rewrite. Use numbers only when they are in the resume or the user gives them; otherwise mark the gap as `[number?]` and ask.
   - **Keywords to add**, only ones the user can honestly claim.
   - **Interview rate estimate** for these targets, before and after the fixes.
4. No flattery. Plain language: {{writing_rules_inline}}
5. Offer to write the updated resume to `resume/resume.md` and export it, and keep the original file untouched.
