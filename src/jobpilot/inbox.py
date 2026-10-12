"""`jobpilot inbox`: read recent mail (read only) and update application statuses.

Works with any IMAP mailbox. Gmail and Outlook need an app password (2FA on):
  Gmail:   https://myaccount.google.com/apppasswords   host imap.gmail.com
  Outlook: account security > app passwords           host outlook.office365.com
The mailbox is opened with EXAMINE (read only), so nothing is marked read,
moved, labelled or deleted.
"""
from __future__ import annotations

import email
import imaplib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Dict, Iterable, List, Optional, Tuple

from .config import Workspace
from .models import STATUS_RANK
from .pipeline import norm_company
from .sources.base import strip_html
from .tracker import open_tracker

ACTIVE = {"Applied", "Screening", "Interview", "Offer"}

PATTERNS = {
    "Rejected": [r"unfortunately", r"we regret", r"not (?:been )?selected", r"decided not to", r"not to move forward",
                 r"not moving forward", r"other candidates", r"position has been filled", r"leider", r"absage",
                 r"nicht berücksichtig", r"anderen? (?:kandidat|bewerber)", r"nicht weiter(?:verfolgen| berücksichtigen)",
                 r"gegen sie entschieden", r"keine positive rückmeldung"],
    "Offer": [r"\boffer letter\b", r"pleased to offer", r"job offer", r"\bvertragsangebot", r"arbeitsvertrag",
              r"freuen uns,? ihnen (?:ein|die) (?:angebot|stelle)", r"zusage"],
    "Interview": [r"\binterview\b", r"vorstellungsgespräch", r"kennenlerngespräch", r"invite you to (?:a|an) (?:call|meeting|chat)",
                  r"schedule (?:a|an) (?:call|meeting|time)", r"calendly\.com", r"einladung zum gespräch",
                  r"technical (?:round|call)", r"meet the team"],
    "Screening": [r"coding (?:challenge|test|assessment)", r"take[- ]home", r"hackerrank", r"codility", r"assessment",
                  r"questionnaire", r"online test", r"recruiter call", r"phone screen", r"kurzes telefonat",
                  r"fragebogen", r"telefoninterview"],
    "Applied": [r"(?:thank you|thanks) for (?:your )?appl", r"we(?:'ve| have) received your application",
                r"application (?:has been )?received", r"eingang ihrer bewerbung", r"vielen dank für ihre bewerbung",
                r"bewerbung (?:ist )?eingegangen", r"bestätigung ihrer bewerbung"],
}
ORDER = ["Rejected", "Offer", "Interview", "Screening", "Applied"]
ALERT_SENDERS = ["jobagent", "jobalerts", "job alerts", "jobs-noreply@linkedin", "jobs-listings@linkedin",
                 "alert@indeed", "noreply@stepstone", "newsletter", "jobs@xing"]


@dataclass
class Mail:
    sender: str
    subject: str
    body: str
    when: date
    message_id: str


def _dec(v: Optional[str]) -> str:
    if not v:
        return ""
    try:
        return str(make_header(decode_header(v)))
    except Exception:  # noqa: BLE001
        return v


def _body(msg) -> str:
    parts = []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html") or part.get("Content-Disposition", "").startswith("attachment"):
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        parts.append(strip_html(text) if ctype == "text/html" else text)
    return "\n".join(parts)[:20000]


def fetch_mail(ws: Workspace, days: int) -> List[Mail]:
    host = ws.get("inbox.imap_host", "imap.gmail.com")
    user = ws.get("inbox.username") or ws.get("person.email")
    pw = ws.env.get("JOBPILOT_IMAP_PASSWORD")
    if not (host and user and pw):
        raise RuntimeError("Inbox check needs inbox.imap_host, inbox.username in profile.yaml and "
                           "JOBPILOT_IMAP_PASSWORD in .env (an app password).")
    since = (date.today() - timedelta(days=days)).strftime("%d-%b-%Y")
    out: List[Mail] = []
    with imaplib.IMAP4_SSL(host, int(ws.get("inbox.imap_port", 993))) as imap:
        imap.login(user, pw)
        folders = ws.get("inbox.folders", ["INBOX"]) or ["INBOX"]
        for folder in folders:
            typ, _ = imap.select(f'"{folder}"' if " " in folder else folder, readonly=True)
            if typ != "OK":
                continue
            typ, data = imap.search(None, "SINCE", since)
            if typ != "OK":
                continue
            ids = data[0].split()[-400:]
            for mid in ids:
                typ, msg_data = imap.fetch(mid, "(BODY.PEEK[])")
                if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                try:
                    when = parsedate_to_datetime(msg.get("Date")).date()
                except Exception:  # noqa: BLE001
                    when = date.today()
                out.append(Mail(sender=_dec(msg.get("From")), subject=_dec(msg.get("Subject")), body=_body(msg),
                                when=when, message_id=str(msg.get("Message-ID", "")).strip()))
    return out


def classify(mail: Mail) -> Optional[str]:
    text = f"{mail.subject}\n{mail.body}".lower()
    for status in ORDER:
        if any(re.search(p, text) for p in PATTERNS[status]):
            return status
    return None


def is_alert(mail: Mail) -> bool:
    s = mail.sender.lower()
    return any(a in s for a in ALERT_SENDERS)


def match(mail: Mail, candidates: Iterable[Dict]) -> Tuple[Optional[Dict], int]:
    text = f"{mail.subject}\n{mail.body}".lower()
    sender = mail.sender.lower()
    domain = parseaddr(mail.sender)[1].split("@")[-1].lower()
    best, best_score = None, 0
    for c in candidates:
        score = 0
        ref = str(c.get("Posting Ref") or "")
        if ref and not re.match(r"^(LI|IN|SS|XI|AN|AZ|BA|GH|LV|AB|PE|RC|SR|WEB)-", ref) and ref.lower() in text:
            score += 10
        comp = norm_company(str(c.get("Company") or ""))
        if comp and len(comp) >= 3:
            if comp in norm_company(sender) or comp in domain.replace(".", "").replace("-", ""):
                score += 6
            elif comp in norm_company(mail.subject):
                score += 5
            elif comp in re.sub(r"[^a-z0-9äöüß]+", "", text[:3000]):
                score += 3
        title_words = [w for w in re.findall(r"[a-zäöü]{5,}", str(c.get("Title") or "").lower())
                       if w not in ("working", "student", "werkstudent", "intern", "internship")]
        if title_words and sum(1 for w in title_words if w in text) >= min(2, len(title_words)):
            score += 2
        if score > best_score:
            best, best_score = c, score
    return (best, best_score) if best_score >= 5 else (None, 0)


def run_inbox(ws: Workspace, days: int = 2, mails: Optional[List[Mail]] = None, today: Optional[str] = None,
              quiet: bool = False) -> Dict:
    today = today or date.today().isoformat()
    tracker = open_tracker(ws)
    if mails is None:
        mails = fetch_mail(ws, days)
    jobs = tracker.jobs()
    candidates = [j for j in jobs if str(j["Status"]) in ACTIVE | {"Found", "Shortlisted"}]
    changes: List[Tuple[str, str, str, str]] = []
    actions: List[str] = []
    for m in sorted(mails, key=lambda x: x.when):
        if is_alert(m):
            continue
        status = classify(m)
        if not status:
            continue
        job, strength = match(m, candidates)
        if not job:
            continue
        old = str(job["Status"])
        if status == "Applied" and old not in ("Found", "Shortlisted"):
            continue
        if old in ("Found", "Shortlisted") and status != "Applied" and strength < 6:
            # Only trust a reply about a job never marked as applied when the sender matches the company.
            continue
        if STATUS_RANK.get(status, 0) < STATUS_RANK.get(old, 0):
            continue
        tracker.update_job(job["ID"], {"Status": status}, today)
        summary = f"{status.lower()} mail from {parseaddr(m.sender)[1] or m.sender}: {m.subject[:80]}"
        tracker.prepend_job_note(job["ID"], summary, today)
        next_step = {"Applied": "Wait", "Screening": "Complete the requested step", "Interview": "Confirm a time slot",
                     "Offer": "Review the offer", "Rejected": "None"}[status]
        follow = (date.fromisoformat(today) + timedelta(days=14)).isoformat() if status == "Applied" else ""
        values = {"Status": status, "Last Response Date": m.when.isoformat(), "Next Step": next_step,
                  "Mail Reference": f"{m.subject[:60]} ({m.when.isoformat()})"}
        if status == "Applied":
            values.update({"Applied Date": m.when.isoformat(), "Channel": "Email", "Follow-up Due": follow})
        tracker.upsert_application(job["ID"], values)
        job["Status"] = status
        changes.append((job["ID"], str(job["Company"]), old, status))
        if status in ("Screening", "Interview", "Offer"):
            actions.append(f"{job['ID']} {job['Company']}: {next_step} ({m.subject[:70]})")

    # follow-up and ghosting rules
    follow_ups = []
    for a in tracker.applications():
        if str(a["Status"]) != "Applied" or not a["Applied Date"]:
            continue
        try:
            age = (date.fromisoformat(today) - date.fromisoformat(str(a["Applied Date"])[:10])).days
        except ValueError:
            continue
        if age >= 35:
            tracker.upsert_application(str(a["Job ID"]), {"Status": "Ghosted", "Next Step": "None"})
            try:
                tracker.update_job(str(a["Job ID"]), {"Status": "Ghosted"}, today)
            except KeyError:
                pass
        elif age >= 21:
            tracker.upsert_application(str(a["Job ID"]), {"Next Step": "Send polite follow-up"})
            follow_ups.append(f"{a['Job ID']} {a['Company']} (applied {age} days ago)")

    tracker.refresh_review_queue()
    tracker.log_run([datetime.now().strftime("%Y-%m-%d %H:%M"), "Inbox check", 0, len(changes), "mail", "",
                     f"{len(mails)} mails scanned, {len(changes)} updates, {len(follow_ups)} follow-ups due"])
    tracker.save()
    result = {"changes": changes, "actions": actions, "follow_ups": follow_ups, "scanned": len(mails)}
    if not quiet:
        print(f"Scanned {len(mails)} mails. {len(changes)} status updates.")
        for a in actions:
            print("ACTION  " + a)
        for jid, comp, old, new in changes:
            print(f"  {jid} {comp}: {old} -> {new}")
        for f in follow_ups:
            print("FOLLOW UP  " + f)
    return result
