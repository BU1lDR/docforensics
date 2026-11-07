"""Read stage: render every page and locate its words, one document at a time."""
from collections.abc import Callable

from ..findings import add_findings, limitation
from ..model import Case, Document, Evidence
from ..pipeline import Ctx, guarded
from ..understand.layout import sideways
from .ocr import Ocr, load_image_page, ocr_page
from .pdf import pdf_meta, read_pdf_page


def _read_pdf_doc(doc: Document, ctx: Ctx, before_ocr: Callable[[], None]) -> None:
    pdf = ctx.cd.root / doc.stored_path
    meta = pdf_meta(pdf)
    pages = []
    for i in range(int(meta["pages"])):
        out = ctx.cd.pages / f"{doc.id}-p{i + 1}.png"
        try:
            page = read_pdf_page(pdf, i, doc.id, out)
            if page.read_mode == "ocr":
                before_ocr()
                ocr_page(page, doc.id, ctx.th)
        except Exception as e:
            raise RuntimeError(f"page {i + 1}: {type(e).__name__}: {e}") from e
        page.image_path = out.relative_to(ctx.cd.root).as_posix()
        pages.append(page)
    doc.meta, doc.pages = meta, pages  # all or nothing: a document with a failed page gets no pages
    doc.kind = "pdf-digital" if all(p.read_mode == "text-layer" for p in pages) else "pdf-scanned"
    ctx.audit.append("system", "doc_read", {"doc": doc.id, "pages": len(pages), "kind": doc.kind,
                                            "words": sum(len(p.words) for p in pages)})


def _read_image_doc(doc: Document, ctx: Ctx, before_ocr: Callable[[], None]) -> None:
    before_ocr()
    out = ctx.cd.pages / f"{doc.id}-p1.png"
    page = load_image_page(ctx.cd.root / doc.stored_path, doc.id, out, ctx.th)
    page.image_path = out.relative_to(ctx.cd.root).as_posix()
    doc.meta, doc.pages = {"pages": "1"}, [page]
    ctx.audit.append("system", "doc_read", {"doc": doc.id, "pages": 1, "kind": doc.kind, "words": len(page.words)})


def read_stage(case: Case, ctx: Ctx) -> None:
    announced = False

    def before_ocr() -> None:
        """Record which OCR models are used, once per run, just before the first page that needs them."""
        nonlocal announced
        if not announced:
            ctx.audit.append("system", "ocr_models", {"engine": "rapidocr", "models": Ocr.shared().model_files()})
            announced = True

    for doc in case.documents:
        read = _read_image_doc if doc.kind == "image" else _read_pdf_doc
        guarded(ctx, case, "read", lambda doc=doc, read=read: read(doc, ctx, before_ocr), doc_id=doc.id)
        for pg in doc.pages:
            if seen := sideways(pg.words):  # a quarter turn is not undone: the page is unreliable, whatever its sharpness
                title, note = f"Page {pg.n} stands on its side", "page stands on its side"
                why = (f"{seen[0]} of the {seen[1]} words of three characters or more on this page are taller than wide, so it was scanned "
                       "or stored a quarter turn. The reader does not turn pages back: its rows are the document's columns and a value "
                       "would pair with the wrong label.")
            elif pg.upside_down:  # nor is a half turn: the words of each row come in the wrong order
                turned, of = pg.upside_down
                title, note = f"Page {pg.n} stands upside down", "page stands upside down"
                how = (f"{turned} of the {of} words of three characters or more in this page's text run right to left, so it was stored "
                       "half a turn." if pg.read_mode == "text-layer" else
                       f"The reader's angle test turned {turned} of the {of} lines it found on this page before reading them, so it was "
                       "scanned or stored half a turn.")
                why = how + " The reader does not turn pages back: the words of each row come in the wrong order and a value would pair with the wrong label or none."
            else:
                continue
            pg.quality_class = "poor"
            add_findings(case, ctx, [limitation(
                "read", title,
                why + " The page is read as poor, so its values carry low confidence and the checks that compare them, the placement of "
                "its words and its marks were not run on it. A copy that stands upright would allow them.",
                [Evidence(doc=doc.id, page=pg.n, box=(0.0, 0.0, float(pg.width), float(pg.height)), note=note)])])
