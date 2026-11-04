"""Checks (design 7.4): functions over the fields extracted from a case, each returning draft findings. An input that is
missing or unreadable is reported as a limitation, never passed over, and the tolerance a check used is printed in its
finding."""
from collections.abc import Callable

from ..config import Thresholds
from ..findings import demote, field_evidence
from ..model import Case, Field, Finding
from ..pipeline import Ctx, guarded

DOUBTFUL = ("degraded", "poor")  # page classes whose OCR digits cannot back a conflict on their own


def observation(detector: str, family: str, title: str, detail: str, evidence: list, conf: float = 1.0) -> Finding:
    """Something worth the reviewer's attention that is neither a conflict nor a limit of the analysis."""
    return Finding(fclass="observation", detector=detector, family=family, title=title, detail=detail, conf=conf,
                   evidence=evidence)


def poor_page(case: Case, f: Field) -> bool:
    """The field was read from a page whose quality was too poor for any value on it to be trusted."""
    return any(p.n == f.page and p.quality_class == "poor" for d in case.documents if d.id == f.doc for p in d.pages)


def usable(case: Case, f: Field) -> bool:
    return f.value is not None and not poor_page(case, f)


def collect(case: Case, ctx: Ctx, checks: list[Callable[[Case, Thresholds], list[Finding]]]) -> list[Finding]:
    """Run each check(case, th) under guarded() and return the drafts of those that finished. One that fails or times out
    is already a limitation by then, and the others still run."""
    drafts: list[Finding] = []
    for check in checks:
        got: list[Finding] = []  # its own list: a check abandoned after a timeout cannot add to the result later
        if guarded(ctx, case, check.__name__, lambda check=check, got=got: got.extend(check(case, ctx.th))):
            drafts += got
    return drafts


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
    from .context import run_context_rules  # lazy: these import the helpers above
    from .cross import run_cross_checks
    from .within import run_within_checks
    run_within_checks(case, ctx)  # inside each document, then across them, then against reference limits
    run_cross_checks(case, ctx)
    run_context_rules(case, ctx)
