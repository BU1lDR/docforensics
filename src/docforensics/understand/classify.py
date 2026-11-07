"""Classification (design 7.3): keyword weights over page 1. A page that fits no type, or two types equally, stays unknown."""
from ..config import Thresholds
from ..model import Case, Document, Page
from ..pipeline import Ctx, guarded
from .layout import find_phrase, lines_of
from .specs import TypeSpec, load_specs


def classify(pages: list[Page], specs: dict[str, TypeSpec], th: Thresholds | None = None) -> tuple[str, float]:
    """(type, share of that type's keyword weight found on page 1). Keywords match fuzzily, so a scan's small misreads do
    not lose them. ('unknown', best share) when no type reaches its min_score or the best two score the same."""
    if not pages:
        return "unknown", 0.0
    floor = (th or Thresholds()).label_sim
    words = [w for line in lines_of(pages[0]) for w in line.words]
    scored = []  # (weight found, share, spec)
    for spec in specs.values():
        got = sum(wt for kw, wt in spec.keywords.items() if any(find_phrase(words, alt, floor) for alt in kw.split("|")))
        total = sum(spec.keywords.values())
        scored.append((got, got / total if total else 0.0, spec))
    share = max((s for _, s, _ in scored), default=0.0)
    fits = sorted((x for x in scored if x[0] >= x[2].min_score), key=lambda x: -x[0])
    if not fits or (len(fits) > 1 and fits[0][0] == fits[1][0]):
        return "unknown", share
    return fits[0][2].type, fits[0][1]


def _classify_doc(doc: Document, specs: dict[str, TypeSpec], ctx: Ctx) -> None:
    doc.doc_type, doc.type_conf = classify(doc.pages, specs, ctx.th)
    ctx.audit.append("system", "doc_classified", {"doc": doc.id, "type": doc.doc_type, "conf": round(doc.type_conf, 3)})


def classify_stage(case: Case, ctx: Ctx) -> None:
    specs = load_specs()
    for doc in case.documents:
        if doc.pages:  # a document that was never read has nothing to classify; the read step has already reported it
            guarded(ctx, case, "classify", lambda doc=doc: _classify_doc(doc, specs, ctx), doc_id=doc.id)
