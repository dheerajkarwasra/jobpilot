"""Core data types."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

STATUSES = ["Found", "Shortlisted", "Applied", "Screening", "Interview", "Offer",
            "Rejected", "Ghosted", "Withdrawn", "Skipped"]
# Pipeline order used to prevent downgrades (e.g. Interview must not go back to Applied).
STATUS_RANK = {"Found": 0, "Shortlisted": 1, "Skipped": 1, "Applied": 2, "Screening": 3,
               "Interview": 4, "Offer": 5, "Rejected": 6, "Ghosted": 6, "Withdrawn": 6}

JOB_COLUMNS = ["ID", "Status", "Fit", "Score", "Company", "Title", "Posting Ref", "Type", "Location",
               "Work Mode", "Posting Language", "Language Required", "Posted Date", "Date Found",
               "Source", "Link", "Notes", "Applied Date", "Last Update"]

APPLICATION_COLUMNS = ["Job ID", "Company", "Title", "Posting Ref", "Applied Date", "Channel",
                       "Documents Sent", "Contact Person", "Status", "Last Response Date",
                       "Next Step", "Follow-up Due", "Mail Reference", "Notes", "Interview Date"]

RUNLOG_COLUMNS = ["Run Time", "Task", "New Postings", "Updated Records", "Sources OK",
                  "Sources Failed", "Notes"]

WATCHLIST_COLUMNS = ["Company", "Active", "ATS", "Slug", "Why", "Last Checked"]


@dataclass
class Job:
    """A single posting as it moves through the pipeline."""
    title: str
    company: str
    link: str
    source: str
    location: str = ""
    description: str = ""
    posted_date: str = ""          # YYYY-MM-DD
    posting_ref: str = ""
    employment_hint: str = ""      # raw employment type text from the source
    remote_hint: Optional[bool] = None
    # Filled by the pipeline
    type: str = ""
    work_mode: str = "Unknown"
    posting_language: str = ""
    language_required: str = "Unknown"
    score: int = 0
    fit: str = ""
    notes: str = ""
    reasons: list = field(default_factory=list)

    def to_row(self, job_id: str, today: str) -> list:
        return [job_id, "Found", self.fit, self.score, self.company, self.title, self.posting_ref,
                self.type, self.location, self.work_mode, self.posting_language,
                self.language_required, self.posted_date, today, self.source, self.link,
                self.notes, "", today]

    def as_dict(self) -> dict:
        return asdict(self)
