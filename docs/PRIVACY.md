# Privacy and security

## What stays where

- **Your workspace** (default `~/JobPilot`): profile, resume, tracker, generated documents. Only on your computer, unless you choose Google Sheets for the tracker
- **`.env` in the workspace**: API keys and the mail app password, readable only by your user (chmod 600 on macOS and Linux)
- **The installed code** (`~/.jobpilot`): no personal data

JobPilot has no server and sends no telemetry. Network calls go only to the job sources you turned on, Google Sheets if chosen, and your mail server if the inbox check is on.

## What your AI assistant sees

When you use Claude Code, Codex or Gemini in the workspace, the assistant reads your profile and resume to do its job, and that text is sent to the model provider like any other prompt. The instruction files tell the assistant never to print or commit `.env`.

## Mail

The inbox check is read only by design (IMAP EXAMINE and BODY.PEEK). Use an app password, which you can revoke any time without changing your main password. Mail content is not stored. Only a dated one line note goes into the tracker.

## Git

The workspace has a `.gitignore` covering `.env`, service account keys, the tracker, resume and applications. If you put the workspace in git, check `git status` before your first commit.

## Sharing JobPilot

The repository contains no personal data. Examples use made up people. If you fork it, keep it that way.

## Reporting a problem

Open a GitHub issue, or for anything sensitive, contact the maintainer privately first.
