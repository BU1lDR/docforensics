"""Checks (design 7.4): functions over the fields extracted from a case, each returning draft findings. An input that is
missing or unreadable is reported as a limitation, never passed over, and the tolerance a check used is printed in its
finding."""
from ..config import Thresholds
from ..findings import demote, field_evidence
from ..model import Case, Field, Finding
from ..pipeline import Ctx

DOUBTFUL = ("degraded", "poor")  # page classes whose OCR digits cannot back a conflict on their own


def inconsistency(detector: str, family: str, title: str, detail: str, cited: list[tuple[Field, str]]) -> Finding:
    """An inconsistency that cites these (field, note) pairs, the first being where to look first. It is as certain as the
    least certain field it rests on."""
    return Finding(fclass="inconsistency", detector=detector, family=family, title=title, detail=detail,
                   conf=min(f.conf for f, _ in cited), evidence=[field_evidence(f, note) for f, note in cited])


def maybe_demote(case: Case, f: Finding, th: Thresholds) -> Finding:
    """An inconsistency that rests on a doubtful reading is shown as a limitation to verify, not as a conflict: its
    confidence is under LOW_CONF, or one of its numbers was read by OCR from a degraded or poor page."""
    if f.fclass != "inconsistency":
        return f
    if f.conf < th.low_conf:
        return demote(f, f"The values may be misread: the least certain of them has confidence {f.conf:.2f}, "
                         f"under the {th.low_conf:g} needed to call it a conflict")
    pages = {(d.id, p.n): p for d in case.documents for p in d.pages}
    for e in f.evidence:  # page 0 (a whole document) is not in the table
        p = pages.get((e.doc, e.page))
        if p and p.read_mode == "ocr" and p.quality_class in DOUBTFUL:
            return demote(f, f"The values were read by OCR from a {p.quality_class} page (page {p.n}) and may be misread")
    return f


def run_checks(case: Case, ctx: Ctx) -> None:
    from .within import run_within_checks  # lazy: within imports the helpers above
    run_within_checks(case, ctx)
