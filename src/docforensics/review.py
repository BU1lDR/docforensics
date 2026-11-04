"""Reviewer actions (design 7.8): a person sets a finding's status and note. The pipeline never does. Each action is saved with the
case and written to the audit trail as the reviewer, with the status before and after. A finding's class is not touched."""
from typing import get_args

from .model import Case, Finding, Status
from .pipeline import Ctx
from .store import save_case

STATUSES = get_args(Status)
MAX_NOTE = 2000


def apply_review(case: Case, ctx: Ctx, finding_id: str, status: str | None = None, note: str | None = None) -> Finding:
    """Set a finding's status, its note, or both. A note replaces the earlier one (the audit trail keeps what it said); an empty note
    clears it. Bad input raises ValueError and an unknown finding KeyError, with nothing changed, saved or logged."""
    if status is None and note is None:
        raise ValueError("give a status, a note, or both")
    if status is not None and status not in STATUSES:
        raise ValueError(f"unknown status {status!r}: use one of {', '.join(STATUSES)}")
    if note is not None and len(note) > MAX_NOTE:
        raise ValueError(f"a note is at most {MAX_NOTE} characters")
    f = next((f for f in case.findings if f.id == finding_id), None)
    if f is None:
        raise KeyError(finding_id)
    before = f.status
    if status is not None:
        f.status = status
    if note is not None:
        f.note = note
    save_case(case, ctx.cd)
    ctx.audit.append("reviewer", "reviewer_action", {"finding": f.id, "from": before, "to": f.status, "note": note})
    return f
