"""Manipulations applied to a genuine PDF (design 8). Each returns the changed file and a Manipulation: what was done and where,
in the 200-DPI pixels the reader reports and with pages counted from 1. That record is the truth the detectors are scored on."""
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .layouts import PX


@dataclass
class Manipulation:
    method: str  # D1.. (design 8)
    doc: str = ""  # which document of a case; the dataset builder fills it in
    page: int = 0  # 1-based; 0 when the change belongs to no page
    box: list[float] | None = None  # 200-DPI px; None when the change has no place on a page
    field: str | None = None  # the extracted field it touches, when the builder knows it
    note: str = ""


def incremental(pdf: bytes, edit: Callable[[pymupdf.Page], object], page: int = 0) -> bytes:
    """The same file with one more revision appended: `edit` is applied to the page (0-based) and saved incrementally."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.pdf"
        path.write_bytes(pdf)
        with pymupdf.open(path) as doc:  # an incremental save needs the original file, not a stream
            edit(doc[page])
            doc.saveIncr()
        return path.read_bytes()


def _find(page: pymupdf.Page, old: str) -> list[tuple[list[dict], dict]]:
    """Every place `old` stands as whole words in one line of the page: its characters, and the span of the first one."""
    hits = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", ()):
            chars = [(c, s) for s in line["spans"] for c in s["chars"]]
            text = "".join(c["c"] for c, _ in chars)
            i = text.find(old) if old else -1
            while i >= 0:
                j = i + len(old)
                if (i == 0 or text[i - 1].isspace()) and (j == len(text) or text[j].isspace()):
                    hits.append(([c for c, _ in chars[i:j]], chars[i][1]))
                i = text.find(old, i + 1)
    return hits


def retype(page: pymupdf.Page, old: str, new: str) -> list[float]:
    """Take `old` (whole words, standing once on the page) out and write `new` where it stood, in the same font, size and
    colour with the same left edge. Returns the box of `new` in 200-DPI px."""
    hits = _find(page, old)
    if len(hits) != 1:
        raise ValueError(f"{old!r} must stand exactly once on the page; found {len(hits)}")
    chars, span = hits[0]
    x0, y0 = chars[0]["origin"][0], min(c["bbox"][1] for c in chars)
    x1, y1 = max(c["bbox"][2] for c in chars), max(c["bbox"][3] for c in chars)
    page.add_redact_annot(pymupdf.Rect(x0 + 0.5, y0 + 0.5, x1 - 0.5, y1 - 0.5))  # inside the glyph boxes: neighbours stay
    page.apply_redactions(images=0, graphics=0)  # text only: no image pixels or ruled lines go with it
    font = "hebo" if "bold" in span["font"].lower() else "helv"  # the two faces every layout is drawn in
    page.insert_text(chars[0]["origin"], new, fontname=font, fontsize=span["size"], color=pymupdf.sRGB_to_pdf(span["color"]))
    width = pymupdf.Font(font).text_length(new, fontsize=span["size"])
    return [round(v * PX, 2) for v in (x0, y0, x0 + width, y1)]


def d1_incremental_edit(pdf: bytes, old: str, new: str, page: int = 0) -> tuple[bytes, Manipulation]:
    """D1: `old` is taken out and `new` written in its place, and the file saved as a new revision on top of the original,
    which stays inside it."""
    box: list[float] = []
    out = incremental(pdf, lambda pg: box.extend(retype(pg, old, new)), page)
    return out, Manipulation("D1", page=page + 1, box=box, note=f"{old!r} replaced by {new!r} in an incremental save")
