"""Forensic detectors (design 7.5). A detector is a function over one document that returns draft findings. Digital detectors
read PDFs that have a text layer, scan detectors read pages that were OCR'd; a document gets the kinds its pages call for.
Each runs on its own under guarded(), so one that fails becomes a limitation and the others still run."""
from collections.abc import Callable

from ..findings import add_findings
from ..model import Case, Document, Finding
from ..pipeline import Ctx, guarded
from .marks import compare_marks
from .pdf_fonts import font_outliers
from .pdf_meta import metadata_observations
from .pdf_overlay import covered_or_hidden_text
from .pdf_revisions import revision_diff
from .scan_layout import layout_consistency
from .scan_noise import noise_residual
from .signature import compare_signatures

Detector = Callable[[Case, Document, Ctx], list[Finding]]
DIGITAL_DETECTORS: list[Detector] = [revision_diff, covered_or_hidden_text, font_outliers, metadata_observations]
SCAN_DETECTORS: list[Detector] = [noise_residual, layout_consistency]


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
    for compare in (compare_signatures, compare_marks):  # signatures and marks are compared across the documents, so once for the case
        drafts = []
        if guarded(ctx, case, f"forensics.{compare.__name__}", lambda compare=compare, drafts=drafts: drafts.extend(compare(case, ctx))):
            add_findings(case, ctx, drafts)
