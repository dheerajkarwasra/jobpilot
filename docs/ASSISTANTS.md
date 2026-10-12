# Using JobPilot with your AI assistant

JobPilot does not call any AI model itself. It finds and tracks jobs, and it writes instruction files so the assistant you already use knows your profile, your rules and the `jobpilot` commands. Open your workspace folder in the assistant and start talking.

Pick assistants during setup, or change them later:

```bash
jobpilot assistants --targets claude,codex,gemini,projects,claude_app
```

Run `jobpilot assistants` again after you edit `profile.yaml` or your resume so the files stay current.

## Claude Code

Files: `CLAUDE.md` and `.claude/skills/jobpilot-*/SKILL.md`

```bash
cd ~/JobPilot
claude
```

Commands: `/jobpilot-search`, `/jobpilot-review`, `/jobpilot-apply J0012`, `/jobpilot-track`. Claude also picks the right skill on its own when you paste a job link.

Claude Code asks before running shell commands. Allow `jobpilot` commands for the session to keep it smooth.

## Codex CLI

Files: `AGENTS.md` and `.agents/skills/jobpilot-*/SKILL.md`

```bash
cd ~/JobPilot
codex
```

Skills are invoked with a dollar sign: `$jobpilot-apply J0012`, or type `/skills` to pick one. Codex also loads a skill when your request matches its description.

## Gemini CLI

Files: `GEMINI.md`, `.gemini/commands/jobpilot-*.toml` and the shared `.agents/skills`

```bash
cd ~/JobPilot
gemini
```

Commands: `/jobpilot-search`, `/jobpilot-apply J0012` and so on.

## Claude or ChatGPT Projects (no terminal)

Setup writes `exports/PROJECT_INSTRUCTIONS.md`. Create a Project, paste that file into the project instructions and upload your resume. The assistant then follows the same workflow for any job you paste. It cannot run `jobpilot` commands, so keep the tracker updated yourself or from a terminal.

## Claude app with connectors (runs in the cloud)

Target `claude_app` writes `exports/CLAUDE_APP_SETUP.md`: a guide plus ready prompts for a Google Sheets tracker, a scheduled job search and a read only Gmail check, all filled in from your profile. See [CLAUDE_APP.md](CLAUDE_APP.md).

## Other assistants

Any agent that reads `AGENTS.md` (Cursor, Windsurf, Aider, OpenCode and others) works with the Codex target. The files are plain Markdown, so you can also copy them into whatever your tool reads.

## What the assistant does for a job

1. Fetches the posting (or asks you to paste it) and saves it to `job-descriptions/`
2. Asks once which documents you want and in which format
3. Gives the assessment every time: chances, a fit table, line by line resume changes and red flags
4. Judges like a senior hiring manager at that kind of company and says what would get you rejected in 30 seconds
5. Writes the documents to `applications/<company>/` and exports DOCX or PDF
6. Marks the job Applied in the tracker once you confirm

All of it is in the instruction file, so you can change any step there or, better, in the templates (see CUSTOMIZE.md).
