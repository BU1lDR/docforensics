"""Manipulations applied to a genuine PDF (design 8). Each returns the changed file and a Manipulation: what was done and where,
in the 200-DPI pixels the reader reports and with pages counted from 1. That record is the truth the detectors are scored on.
C1 to C5 act on the identity or on the list of files instead of on a PDF: a document is drawn from the changed identity, so
what differs is one document's content against the others', and there is no box to record."""
import io
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image

from .fictional import Identity
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


ARIAL = {"helv": Path("C:/Windows/Fonts/arial.ttf"), "hebo": Path("C:/Windows/Fonts/arialbd.ttf")}  # generator only, never shipped; D3 needs them


def _geometry(page: pymupdf.Page, old: str) -> tuple[pymupdf.Point, dict, pymupdf.Rect]:
    """The one place `old` stands as whole words: the origin of its first character, the span it is in, and its box in points."""
    hits = _find(page, old)
    if len(hits) != 1:
        raise ValueError(f"{old!r} must stand exactly once on the page; found {len(hits)}")
    chars, span = hits[0]
    box = pymupdf.Rect(chars[0]["origin"][0], min(c["bbox"][1] for c in chars), max(c["bbox"][2] for c in chars), max(c["bbox"][3] for c in chars))
    return pymupdf.Point(chars[0]["origin"]), span, box


def _px(r: pymupdf.Rect) -> list[float]:
    return [round(v * PX, 2) for v in (r.x0, r.y0, r.x1, r.y1)]


def _rewritten(pdf: bytes, edit: Callable[[pymupdf.Page], object], page: int = 0) -> bytes:
    """The PDF saved afresh after edit(page): unlike `incremental`, no earlier revision stays inside the file."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        edit(doc[page])
        return doc.tobytes()


def _cover_and_write(pg: pymupdf.Page, old: str, new: str, alt: dict[str, Path] | None = None) -> list[float]:
    """Draw a white rectangle over `old`, which stays in the file underneath, and write `new` over it at the same place, size and
    colour: in the page's own face, or in the file of the same face in `alt`. Returns the box of `new` in 200-DPI px."""
    origin, span, box = _geometry(pg, old)
    face = "hebo" if "bold" in span["font"].lower() else "helv"
    if alt:
        pg.insert_font(fontname="alt", fontfile=str(alt[face]))
        width = pymupdf.Font(fontfile=str(alt[face])).text_length(new, fontsize=span["size"])
    else:
        width = pymupdf.Font(face).text_length(new, fontsize=span["size"])
    pg.draw_rect(pymupdf.Rect(box.x0 - 0.5, box.y0, max(box.x1, box.x0 + width) + 0.5, box.y1), color=None, fill=(1, 1, 1))
    pg.insert_text(origin, new, fontname="alt" if alt else face, fontsize=span["size"], color=pymupdf.sRGB_to_pdf(span["color"]))
    return _px(pymupdf.Rect(box.x0, box.y0, box.x0 + width, box.y1))


def d2_cover_retype(pdf: bytes, old: str, new: str, page: int = 0) -> tuple[bytes, Manipulation]:
    """D2: `old` hidden under a white rectangle and `new` written over it in the same font. The old text is still in the file."""
    box: list[float] = []
    out = _rewritten(pdf, lambda pg: box.extend(_cover_and_write(pg, old, new)), page)
    return out, Manipulation("D2", page=page + 1, box=box, note=f"{old!r} covered by a white rectangle and {new!r} written over it in the same font")


def d3_near_font_retype(pdf: bytes, old: str, new: str, page: int = 0) -> tuple[bytes, Manipulation]:
    """D3: as D2, but `new` is written in Arial, which looks like the Helvetica the layouts use."""
    if not all(p.is_file() for p in ARIAL.values()):
        raise FileNotFoundError("D3 needs Arial and Arial Bold from the Windows fonts folder")
    box: list[float] = []
    out = _rewritten(pdf, lambda pg: box.extend(_cover_and_write(pg, old, new, ARIAL)), page)
    return out, Manipulation("D3", page=page + 1, box=box, note=f"{old!r} covered by a white rectangle and {new!r} written over it in Arial")


def d4_metadata_edit(pdf: bytes, producer: str, mod_date: str) -> tuple[bytes, Manipulation]:
    """D4: the producer and the modification date of the file set to these (`mod_date` as PDF writes it, D:YYYYMMDDHHMMSS+05'30')."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        doc.set_metadata({**{k: v for k, v in doc.metadata.items() if v}, "producer": producer, "modDate": mod_date})
        out = doc.tobytes()
    return out, Manipulation("D4", note=f"producer set to {producer!r} and modification date to {mod_date}")


def _text_png(text: str, face: str, size: float, rect: pymupdf.Rect, origin: pymupdf.Point) -> bytes:
    """`text` as a picture the size of `rect`, black on white, standing where it would on the page."""
    with pymupdf.open() as scratch:
        pg = scratch.new_page(width=rect.width, height=rect.height)
        pg.insert_text((origin.x - rect.x0, origin.y - rect.y0), text, fontname=face, fontsize=size)
        return pg.get_pixmap(dpi=300).tobytes("png")


def d5_paste_image(pdf: bytes, old: str, new: str, page: int = 0) -> tuple[bytes, Manipulation]:
    """D5: a picture of `new` placed over `old`, which stays in the file underneath."""
    box: list[float] = []

    def edit(pg: pymupdf.Page) -> None:
        origin, span, b = _geometry(pg, old)
        face = "hebo" if "bold" in span["font"].lower() else "helv"
        width = pymupdf.Font(face).text_length(new, fontsize=span["size"])
        rect = pymupdf.Rect(b.x0 - 1, b.y0 - 1, max(b.x1, b.x0 + width) + 1, b.y1 + 1)
        pg.insert_image(rect, stream=_text_png(new, face, span["size"], rect, origin))
        box.extend(_px(rect))

    out = _rewritten(pdf, edit, page)
    return out, Manipulation("D5", page=page + 1, box=box, note=f"a picture of {new!r} placed over {old!r}")


# --- scans: S1 and S2 act on a finished scan (a JPEG at 200 DPI) and end with one more JPEG save at quality 85

def _gray(jpeg: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("L")).copy()


def _jpeg(a: np.ndarray) -> bytes:
    out = io.BytesIO()
    Image.fromarray(a).save(out, "JPEG", quality=85)
    return out.getvalue()


def _inside(a: np.ndarray, box: list[float]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return max(int(round(x0)), 0), max(int(round(y0)), 0), min(int(round(x1)), a.shape[1]), min(int(round(y1)), a.shape[0])


def s1_splice(scan: bytes, donor_scan: bytes, box: list[float]) -> tuple[bytes, Manipulation]:
    """S1: the same place on another scan of the same size pasted into `box` (200-DPI px of the scan)."""
    a, donor = _gray(scan), _gray(donor_scan)
    if donor.shape != a.shape:
        raise ValueError("the donor scan must be the same size as the scan")
    x0, y0, x1, y1 = _inside(a, box)
    a[y0:y1, x0:x1] = donor[y0:y1, x0:x1]
    return _jpeg(a), Manipulation("S1", page=1, box=[float(v) for v in box], note="the same place on another scan pasted in")


def s2_erase_retype(scan: bytes, box: list[float], new_text: str) -> tuple[bytes, Manipulation]:
    """S2: `box` filled in from its surroundings (cv2.inpaint) and `new_text` written in it: drawn by PyMuPDF in Helvetica, to the
    right edge of the box when it is a number (as the columns of figures are) and to the left edge otherwise, then blurred a little."""
    a = _gray(scan)
    x0, y0, x1, y1 = _inside(a, box)
    mask = np.zeros_like(a)
    mask[y0:y1, x0:x1] = 255
    a = cv2.inpaint(a, mask, 3, cv2.INPAINT_TELEA)
    w, h = x1 - x0, y1 - y0
    wpt, hpt = w * 72 / 200, h * 72 / 200
    size = hpt * 0.85
    gap = 1.0
    x = wpt - gap - pymupdf.Font("helv").text_length(new_text, fontsize=size) if re.fullmatch(r"[\d,.\s-]+", new_text) else gap
    with pymupdf.open() as scratch:
        pg = scratch.new_page(width=wpt, height=hpt)
        pg.insert_text((x, hpt * 0.75), new_text, fontname="helv", fontsize=size)
        pix = pg.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
    patch = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
    patch = cv2.GaussianBlur(cv2.resize(patch, (w, h)), (0, 0), 0.8)
    a[y0:y1, x0:x1] = (a[y0:y1, x0:x1].astype(np.float32) * patch / 255).astype(np.uint8)  # black text on the filled-in paper
    return _jpeg(a), Manipulation("S2", page=1, box=[float(v) for v in box], note=f"the box erased and {new_text!r} written in it")


def c1_consistent_change(ident: Identity, **changes: int) -> Identity:
    """C1: the pay figures changed together, so the payslip adds up on its own. Draw the payslip from the result and the
    statement and the application from the original identity."""
    if not changes or set(changes) - {"monthly_gross", "deductions"}:
        raise ValueError("C1 changes monthly_gross and/or deductions, and nothing else")
    return replace(ident, **changes)


def c2_cross_document(ident: Identity, field: str, new: str) -> Identity:
    """C2: one document drawn with another name, employer, address or month (`new` is an ISO first-of-month date for a month)."""
    if field not in ("name", "employer", "address", "month"):
        raise ValueError(f"C2 changes name, employer, address or month, not {field!r}")
    if field == "name":  # the document says another name; whoever signed it is still the person
        return replace(ident, name=new, hand=ident.hand or ident.name)
    if field != "month":
        return replace(ident, **{field: new})
    day = date.fromisoformat(new)
    if day.day != 1:
        raise ValueError("a month is given as the first day of the month")
    return replace(ident, month=day)


def c3_duplicate(files: list[bytes]) -> list[bytes]:
    """C3: the first file submitted a second time, as the last."""
    if not files:
        raise ValueError("there is no file to submit twice")
    return [*files, files[0]]


def c4_other_hand(ident: Identity, other: Identity) -> Identity:
    """C4: one document signed in another person's hand. Draw that document from the result and the rest from `ident`."""
    return replace(ident, hand=other.name)


def c5_other_mark(ident: Identity, kind: str, strength: str, other: Identity) -> Identity:
    """C5: one document carries another mark: its "logo" or its "stamp", changed "large" (the design of `other`'s bank) or "small" (the
    own design with one thing changed: a ring less in a stamp, one point of a logo moved a tenth). Draw that document from the result."""
    if kind not in ("logo", "stamp"):
        raise ValueError(f"C5 changes the logo or the stamp, not {kind!r}")
    if strength not in ("large", "small"):
        raise ValueError(f"C5 changes a mark large or small, not {strength!r}")
    if strength == "large" and other.bank == ident.bank:
        raise ValueError("another bank's mark is needed: the other identity has the same bank")
    return replace(ident, **{kind: other.bank if strength == "large" else f"{ident.bank}/edit"})
