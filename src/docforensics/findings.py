"""What every stage uses to raise a finding: ids, audit, limitations, demotion."""
from typing import TYPE_CHECKING

from .model import Case, Evidence, Field, Finding

if TYPE_CHECKING:  # pipeline imports this module; the type is only needed for annotations
    from .pipeline import Ctx


def quote(s: str, limit: int = 120) -> str:
    """Document text made safe to print in a finding: one line, no control or bidi characters, cut at `limit`."""
    s = " ".join("".join(c if c.isprintable() else " " for c in s).split())
    return s if len(s) <= limit else s[: limit - 3] + "..."


def doc_evidence(doc_id: str, note: str = "whole document") -> Evidence:
    """Evidence that points at a whole document: page 0 and an empty box. Overlays and crops skip it."""
    return Evidence(doc=doc_id, page=0, box=(0.0, 0.0, 0.0, 0.0), note=note)


def field_evidence(f: Field, note: str = "") -> Evidence:
    """Evidence that points at one extracted field: where it sits and the value read there."""
    return Evidence(doc=f.doc, page=f.page, box=f.box, note=note, field_id=f.id, value=f.value)


def add_findings(case: Case, ctx: "Ctx", drafts: list[Finding]) -> list[Finding]:
    """Give drafts (id "") the next ids F-001.. and log each one."""
    out = []
    for d in drafts:
        f = d.model_copy(update={"id": f"F-{len(case.findings) + 1:03d}"})
        case.findings.append(f)
        ctx.audit.append("system", "finding_created",
                         {"finding": f.id, "detector": f.detector, "fclass": f.fclass, "title": f.title})
        out.append(f)
    return out


def limitation(detector: str, title: str, detail: str, evidence: list[Evidence] | None = None) -> Finding:
    return Finding(fclass="processing_limitation", detector=detector, family="limitation",
                   title=title, detail=detail, evidence=evidence or [])


def demote(f: Finding, reason: str) -> Finding:
    """An inconsistency we cannot trust becomes a limitation: the reader sees it, but not as a conflict."""
    if f.fclass != "inconsistency":
        raise ValueError(f"only an inconsistency can be demoted, not {f.fclass}")
    detail = f"{reason}. Original finding: {f.detail}" if f.detail else reason
    return f.model_copy(deep=True, update={
        "fclass": "processing_limitation", "family": "limitation",
        "title": f"Possible extraction error, verify: {f.title}", "detail": detail})
