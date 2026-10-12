# Automatic runs

```bash
jobpilot schedule install     # add or update the schedule
jobpilot schedule show
jobpilot schedule remove
```

Setup offers this at the end. Times come from `profile.yaml`:

```yaml
schedule:
  search_every_hours: 6       # 0 turns automatic search off
  inbox_daily_at: "07:52"
```

## macOS and Linux

JobPilot adds lines to your user crontab, marked with `# jobpilot`. The search runs at minute 47 every N hours (00:47, 06:47, 12:47, 18:47 for 6 hours). Output goes to `logs/search.log` and `logs/inbox.log` in the workspace.

On macOS, if the log stays empty, give `cron` Full Disk Access (System Settings > Privacy and Security > Full Disk Access, add `/usr/sbin/cron`), or keep the workspace outside Documents and Desktop.

## Windows

JobPilot creates two Task Scheduler tasks, "JobPilot search" and "JobPilot inbox", for your user. See them in Task Scheduler under the root folder.

## Laptops that sleep

A run that falls while the laptop is asleep is skipped and the next one catches up, since each search looks back over several days and duplicates are removed. Nothing is lost.

## Running somewhere else

Any machine with Python can run `jobpilot --workspace PATH search --quiet` on a timer: a home server, a Raspberry Pi, or a scheduled cloud agent. Keep `.env` private there too.
