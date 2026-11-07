"""PDF reader: render a page and read its words, with font, size and colour, from the text layer."""
from collections.abc import Iterator
from pathlib import Path

import pymupdf

from ..model import Page, Word
from ..understand.layout import upside_down

MAX_SIDE_PX = 6000     # longest rendered side; larger pages are rendered at a lower dpi and the dpi is recorded
BAD_SHARE = 0.3        # more than this share of unmapped characters and the layer is not trusted
_FFFD = 0xFFFD
_PRIVATE_USE = (0xE000, 0xF8FF)


def _bad_chars(text: str) -> int:
    if "(cid:" in text:
        return len(text)
    return sum(1 for c in text if ord(c) == _FFFD or _PRIVATE_USE[0] <= ord(c) <= _PRIVATE_USE[1])


def layer_is_usable(words: list[Word]) -> bool:
    """False when the page has no text, or too much of it is unmapped glyphs (U+FFFD, private use, cid tokens)."""
    chars = sum(len(w.text) for w in words)
    return chars > 0 and sum(_bad_chars(w.text) for w in words) / chars <= BAD_SHARE


def _mostly_invisible(page: pymupdf.Page) -> bool:
    """Scanner apps put an invisible (render mode 3) OCR layer over the page image: that is a scan, not a digital page."""
    total = invisible = 0
    for span in page.get_texttrace():
        total += len(span["chars"])
        if span["type"] == 3:
            invisible += len(span["chars"])
    return total > 0 and invisible / total > 0.9


def _runs(page: pymupdf.Page) -> Iterator[list[tuple[dict, dict]]]:
    """Characters of the text layer, split on whitespace, as (char, span) pairs."""
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", ()):
            run: list[tuple[dict, dict]] = []
            for span in line["spans"]:
                for ch in span["chars"]:
                    if ch["c"].isspace():
                        if run:
                            yield run
                        run = []
                    else:
                        run.append((ch, span))
            if run:
                yield run


def _leftward(page: pymupdf.Page) -> tuple[int, int]:
    """(words that run right to left, words counted) among the words of three characters or more of an open page, as the page is shown:
    a page stored or drawn half a turn has most of them run leftwards. Characters of a word come in the order they were written."""
    left = total = 0
    for run in _runs(page):
        if len(run) >= 3:
            a, b = (pymupdf.Point(*run[i][0]["origin"]) * page.rotation_matrix for i in (0, -1))
            total += 1
            left += b.x - a.x < -abs(b.y - a.y)
    return left, total


def _word(run: list[tuple[dict, dict]], wid: str, rot: pymupdf.Matrix, scale: float) -> Word:
    # extraction coordinates are those of the unrotated page; rotation_matrix maps them onto the rendered one
    r = pymupdf.Rect(min(c["bbox"][0] for c, _ in run), min(c["bbox"][1] for c, _ in run),
                     max(c["bbox"][2] for c, _ in run), max(c["bbox"][3] for c, _ in run)) * rot
    span = run[0][1]  # a word that changes font part-way takes the first character's style
    return Word(id=wid, text="".join(c["c"] for c, _ in run), box=tuple(v * scale for v in r), pt_box=tuple(r),
                font=span["font"], size=span["size"], color=f"#{span['color']:06x}")


def page_words(page: pymupdf.Page, prefix: str, scale: float) -> list[Word]:
    """The words of an open page's text layer, with boxes in the pixels of the page rendered at 72 * scale dpi."""
    return [_word(run, f"{prefix}-w{k}", page.rotation_matrix, scale) for k, run in enumerate(_runs(page), 1)]


def read_pdf_page(pdf: Path, index: int, doc_id: str, out_png: Path, dpi: int = 200) -> Page:
    """Render page `index` (0-based) to out_png and read its words. A page without a usable text layer is
    marked for OCR with no words and quality_class "poor" until the OCR step has measured it."""
    with pymupdf.open(pdf) as doc:
        page = doc[index]
        dpi = max(1, min(dpi, int(MAX_SIDE_PX * 72 / max(page.rect.width, page.rect.height, 1))))
        scale = dpi / 72
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        pix.save(str(out_png))
        n = index + 1
        words = page_words(page, f"{doc_id}-p{n}", scale)
        usable = layer_is_usable(words) and not _mostly_invisible(page)
        return Page(n=n, width=pix.width, height=pix.height, dpi=dpi, image_path=Path(out_png).as_posix(),
                    read_mode="text-layer" if usable else "ocr", quality_class="text-layer" if usable else "poor",
                    words=words if usable else [], upside_down=upside_down(*_leftward(page)) if usable else None)


def pdf_meta(pdf: Path) -> dict[str, str]:
    with pymupdf.open(pdf) as doc:
        m = doc.metadata or {}
        out = {k: str(m.get(k) or "") for k in ("producer", "creator", "creationDate", "modDate", "format")}
        out["pages"] = str(doc.page_count)
        return out
