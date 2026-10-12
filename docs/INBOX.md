# Inbox check

Once a day JobPilot reads recent mail and updates the tracker when a company replies: received confirmations, coding tests, interview invitations, offers and rejections, in English and German.

## It is read only

JobPilot opens folders with IMAP EXAMINE and fetches with BODY.PEEK. It cannot send, reply, move, label, delete, or even mark mail as read. Mail bodies are never written to disk. Only a short note (date, type, sender) goes into the tracker.

## Gmail

1. Turn on 2 Step Verification for your Google account
2. Open myaccount.google.com/apppasswords, create an app password named JobPilot
3. Enter the 16 letter password in setup (without spaces). Your normal password does not work here

IMAP host: `imap.gmail.com`

## Outlook.com and Microsoft 365

Personal Outlook accounts: create an app password under account.microsoft.com > Security > Advanced security options. Host: `outlook.office365.com`.

Work or university Microsoft 365 accounts often block IMAP with passwords. If login fails, forward replies to a Gmail address or skip the inbox check.

## Other providers

Choose "Other IMAP" and enter the host. Port 993 with SSL is used. Change it in `profile.yaml` with `inbox.imap_port`.

## How matching works

1. Each mail is classified as Applied, Screening, Interview, Offer or Rejected using phrase lists. Job alert newsletters are ignored
2. It is matched to a tracked job by company name, sender domain, job title and Posting Ref. A weak match is ignored rather than guessed
3. The job status moves forward, never backward, and a dated note is added
4. Applications with no reply get "Send polite follow-up" after 21 days and become Ghosted after 35 days

Run it by hand:

```bash
jobpilot inbox --days 7
```

## Settings

```yaml
inbox:
  enabled: true
  imap_host: imap.gmail.com
  username: you@example.com
  folders: ["INBOX"]          # add "[Gmail]/All Mail" to include archived mail
```

The password lives only in `.env` as `JOBPILOT_IMAP_PASSWORD`.
