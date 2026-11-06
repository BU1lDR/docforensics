"""Reviewer decisions (Task 28): what a person decided about each finding of a case, and a count per detector.

The decisions are read from the audit trail, not from case.json: the trail is hash-chained and signed, and a case whose trail does not
verify, or does not agree with its signed checkpoints, is refused instead of exported. Nothing is learned from them. They are for a person
who reads the counts and edits a threshold file by hand. A dismissal is one person's judgement, not proof of a false alarm, and the counts
are not accuracy figures: they cover whatever was reviewed, by whoever reviewed it."""
import json
from pathlib import Path

from .audit import AuditLog
from .review import STATUSES
from .signing import signing_view
from .store import CASE_ID_RE, CaseDir, load_case

KEYS = ("case", "finding", "detector", "class", "status", "note", "actions", "last_action")
_BLANK = {"status": "open", "note": "", "actions": 0, "last_action": None}  # a finding nobody has acted on


def case_dirs(data_root: Path | str) -> list[CaseDir]:
    """The cases under data_root/cases, sorted by id (the date comes first): folders named like a case id that hold a case.json."""
    base = Path(data_root) / "cases"
    if not base.is_dir():
        return []
    return [CaseDir(p) for p in sorted(base.iterdir()) if CASE_ID_RE.fullmatch(p.name) and (p / "case.json").is_file()]


def decisions(cd: CaseDir) -> list[dict]:
    """One row per finding of the case, with the decision the audit trail records: the last status set, the last note set, how many times
    a person acted and when they last did (the trail's own time stamp). Rows hold ids, a detector name, a class and the reviewer's note;
    no finding title and no text from a document. A trail that is broken, missing, empty or out of line with its checkpoints raises
    ValueError: it is not read as "no decisions"."""
    audit = AuditLog(cd.audit_path)
    ok, bad = audit.verify()
    if not ok:
        raise ValueError(f"the audit trail of {cd.id} does not verify (broken at event {bad}): decisions are read from it, so none are exported")
    events = audit.events()
    if not events:
        raise ValueError(f"the audit trail of {cd.id} is missing or empty: decisions are read from it, so none are exported")
    sig = signing_view(cd)
    if sig["problem"]:
        raise ValueError(f"the audit trail of {cd.id} does not agree with its signed checkpoints ({sig['problem']}): none exported")
    state: dict[str, dict] = {}
    for e in events:
        fid = e.data.get("finding")
        if e.event != "reviewer_action" or e.actor != "reviewer" or not isinstance(fid, str):
            continue
        s = state.setdefault(fid, dict(_BLANK))
        if e.data.get("to") in STATUSES:
            s["status"] = e.data["to"]
        if isinstance(e.data.get("note"), str):  # a status-only action records no note, and leaves the earlier one
            s["note"] = e.data["note"]
        s["actions"] += 1
        s["last_action"] = e.ts
    return [{"case": cd.id, "finding": f.id, "detector": f.detector, "class": f.fclass, **state.get(f.id, _BLANK)}
            for f in load_case(cd).findings]


def tally(rows: list[dict]) -> list[dict]:
    """Per detector and class: how many findings were raised and how many stand at each status now. Counts only: no rate, no score.
    The class is part of the key so that observations and potential manipulations of one detector are not mixed."""
    out: dict[tuple[str, str], dict[str, int]] = {}
    for r in rows:
        out.setdefault((r["detector"], r["class"]), dict.fromkeys(STATUSES, 0))[r["status"]] += 1
    return [{"detector": d, "class": c, "raised": sum(t.values()), **t} for (d, c), t in sorted(out.items())]


def jsonl(rows: list[dict]) -> str:
    """One JSON object per line, ASCII only: control and bidi characters in a note are escaped (DEL too, which JSON leaves raw), so the
    file is inert when it is printed or opened in a terminal."""
    return "".join(json.dumps(r, ensure_ascii=True).replace("\x7f", "\\u007f") + "\n" for r in rows)
