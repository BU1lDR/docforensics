"""Read stage: render every page and locate its words, one document at a time."""
from ..model import Case, Document
from ..pipeline import Ctx, guarded
from .pdf import pdf_meta, read_pdf_page


def _read_pdf_doc(doc: Document, ctx: Ctx) -> None:
    pdf = ctx.cd.root / doc.stored_path
    meta = pdf_meta(pdf)
    pages = []
    for i in range(int(meta["pages"])):
        out = ctx.cd.pages / f"{doc.id}-p{i + 1}.png"
        try:
            page = read_pdf_page(pdf, i, doc.id, out)
        except Exception as e:
            raise RuntimeError(f"page {i + 1}: {type(e).__name__}: {e}") from e
        page.image_path = out.relative_to(ctx.cd.root).as_posix()
        pages.append(page)
    doc.meta, doc.pages = meta, pages  # all or nothing: a document with a failed page gets no pages
    doc.kind = "pdf-digital" if all(p.read_mode == "text-layer" for p in pages) else "pdf-scanned"
    ctx.audit.append("system", "doc_read", {"doc": doc.id, "pages": len(pages), "kind": doc.kind,
                                            "words": sum(len(p.words) for p in pages)})


def read_stage(case: Case, ctx: Ctx) -> None:
    for doc in case.documents:
        if doc.kind == "image":  # images are read in Task 6
            continue
        guarded(ctx, case, "read", lambda doc=doc: _read_pdf_doc(doc, ctx), doc_id=doc.id)
