"""Forensic detectors (design 7.5). A detector is a function over one document that returns draft findings. Digital detectors
read PDFs that have a text layer, scan detectors read pages that were OCR'd; a document gets the kinds its pages call for.
Each runs on its own under guarded(), so one that fails becomes a limitation and the others still run."""
from collections.abc import Callable

from ..findings import add_findings
from ..model import Case, Document, Finding
from ..pipeline import Ctx, guarded
from .pdf_revisions import revision_diff

Detector = Callable[[Case, Document, Ctx], list[Finding]]
DIGITAL_DETECTORS: list[Detector] = [revision_diff]
SCAN_DETECTORS: list[Detector] = []


def run_forensics(case: Case, ctx: Ctx) -> None:
    for doc in case.documents:
        modes = {p.read_mode for p in doc.pages}
        detectors = [*(DIGITAL_DETECTORS if "text-layer" in modes else ()), *(SCAN_DETECTORS if "ocr" in modes else ())]
        for det in detectors:
            drafts: list[Finding] = []
            if guarded(ctx, case, f"forensics.{det.__name__}", lambda doc=doc, det=det, drafts=drafts: drafts.extend(det(case, doc, ctx)),
                       doc_id=doc.id):
                add_findings(case, ctx, drafts)
                ctx.audit.append("system", "doc_forensics", {"doc": doc.id, "detector": det.__name__, "findings": len(drafts)})
