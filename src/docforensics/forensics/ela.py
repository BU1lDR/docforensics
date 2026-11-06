"""Compression history of a scan (scope D, package E; design 7.5). A scan is a JPEG, and a JPEG that was saved at one quality and then
saved again at a higher one keeps a trace of the first save wherever its picture was not changed: saving it once more at that first
quality alters it far less than at the qualities beside it (the page-wide error has a dip there). A piece that came from another
picture, or text typed where the paper was filled in, has no such trace. The check finds the page's last save as the quality at which
saving again alters it least, finds an earlier save as a dip in the error at a quality at least GAP below that, and reports compact
regions of ink whose error at the earlier quality departs from the page's own and that have no dip of their own there (large bold
type alone only has a larger error; a piece without the earlier save is also flat across the qualities beside it). It sees nothing when the page was saved once, when the
last save lies close to the earlier one, or when the edit shares the page's grid and quality, and it says nothing then. Only an
observation: a page assembled from several scans, a stamp or a date added by the scanner, or a picture inserted by a program leaves the
same mark. Qualities are tried in steps of 5 with the standard tables of libjpeg, as Pillow writes them. An earlier save at a quality
between the steps still shows, at a neighbouring or related step (so the quality named is where the trace shows, not always the quality
of the save); an earlier save written with other tables (Photoshop's presets in the one test made, see docs/spike-e-ela.md) shows not at all.
The idea is that of JPEG ghosts (H. Farid, IEEE Transactions on Information Forensics and Security 4(1), 2009); error-level analysis is the same
idea at one assumed quality, and here the quality is searched for. The last-save search, the dip rule and the cell statistics are written for
this project on numpy, OpenCV and Pillow, with no code from the paper or from a library for it."""
import io
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

from ..findings import doc_evidence, limitation
from ..model import Case, Document, Evidence, Finding
from ..pipeline import Ctx

DETECTOR = "ela"
QUALITIES = tuple(range(25, 100, 5))  # the qualities a page is saved at again
GAP = 10         # the earlier save lies at least this far below the last, or the two dips run into one
MIN_DIP = 1.3    # the page's error at the earlier quality is this much below what the qualities beside it give (geometric mean)
INK = 60         # a pixel this much darker than the paper around it is ink
BLOCK = 16       # px: the size of a cell of the map, two JPEG blocks
MIN_INK = 24     # ink pixels a cell needs to be measured
Z = 6.0          # robust z of a cell's error, over the page's cells
MAX_DIP = 1.3    # a cell without the earlier save has no dip of its own: its error is the same at the qualities either side (an unedited cell shows the page's)
MIN_CELLS = 4    # cells of ink in a region that have none of the earlier save's trace
MIN_RATIO = 2.0  # a cell's error at the earlier quality is at least this multiple of the page's median cell
LISTED = 6       # regions named in one finding


@dataclass
class Region:
    box: tuple[float, float, float, float]
    cells: int
    error: float  # mean grey-level change of its ink on saving again at the earlier quality


@dataclass
class Result:
    final: int | None = None     # quality of the page's last save
    earlier: int | None = None   # quality of an earlier save that left a trace
    dip: float = 0.0
    median: float = 0.0          # the page's median cell, in grey levels
    regions: list[Region] = field(default_factory=list)


def _error(gray: np.ndarray, q: int) -> np.ndarray:
    buf = io.BytesIO()
    Image.fromarray(gray).save(buf, "JPEG", quality=q)
    buf.seek(0)
    return np.abs(gray.astype(np.int16) - np.asarray(Image.open(buf).convert("L"))).astype(np.float32)


def ela_regions(gray: np.ndarray) -> Result:
    """The history of a grey page (uint8) and the regions of its ink that do not share the earlier save."""
    ink = cv2.dilate((gray.astype(np.float32) < cv2.medianBlur(gray, 31).astype(np.float32) - INK).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    if ink.sum() < MIN_INK:
        return Result()
    curve = {q: float(_error(gray, q)[ink].mean()) for q in QUALITIES}
    final = min(curve, key=curve.get)
    dips = {q: (curve[q - 5] * curve[q + 5]) ** 0.5 / max(curve[q], 1e-6) for q in QUALITIES[1:-1] if q <= final - GAP}
    if not dips or max(dips.values()) < MIN_DIP:
        return Result(final=final)
    earlier = max(dips, key=dips.get)
    h, w = (gray.shape[0] // BLOCK) * BLOCK, (gray.shape[1] // BLOCK) * BLOCK
    cut = lambda a: a[:h, :w].reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK).sum(axis=(1, 3))
    n = cut(ink.astype(np.float32))
    seen = n >= MIN_INK
    if not seen.any():
        return Result(final, earlier, dips[earlier])
    at = {q: np.where(seen, cut(_error(gray, q) * ink) / np.maximum(n, 1), np.nan) for q in (earlier - 5, earlier, earlier + 5)}
    cell = at[earlier]
    med = float(np.nanmedian(cell))
    mad = float(np.nanmedian(np.abs(cell - med))) * 1.4826 + 1e-6
    own = np.sqrt(at[earlier - 5] * at[earlier + 5]) / np.maximum(cell, 1e-6)  # the page's dip, worked out for each cell on its own
    hit = ((np.where(seen, cell, 0) - med) / mad > Z) & (cell > MIN_RATIO * med) & (own < MAX_DIP)
    closed = cv2.morphologyEx(hit.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    count, lab, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    regions = []
    for i in range(1, count):
        x, y, cw, ch, _area = (int(v) for v in stats[i])
        mine = (lab == i) & seen
        if ((lab == i) & hit).sum() >= MIN_CELLS:
            regions.append(Region((float(x * BLOCK), float(y * BLOCK), float((x + cw) * BLOCK), float((y + ch) * BLOCK)), int(mine.sum()),
                                  float(np.nansum(np.where(mine, cell, 0)) / max(mine.sum(), 1))))
    regions.sort(key=lambda r: -r.cells)
    return Result(final, earlier, dips[earlier], med, regions)


def _why_not(doc: Document, pg, ctx: Ctx) -> str | None:
    """Why this page's pixels are not the saved JPEG's (what follows "page N" in the limitation), or None if they are."""
    try:
        with Image.open(ctx.cd.root / doc.stored_path) as im:
            fmt, size, turn = im.format, im.size, im.getexif().get(274, 1)
    except Exception:
        return "comes from a file that is not a picture, so there is no JPEG save to examine"
    if fmt == "PNG":
        return "is a PNG picture, which is lossless and has no JPEG save to examine"
    if fmt != "JPEG":  # ingest types a file by its first bytes, so this is a JPEG-typed file Pillow reads as another format (a camera's MPO)
        return f"is a picture in the {fmt} format, not a plain JPEG file, so it holds no JPEG save that this check can examine"
    if size != (pg.width, pg.height):
        return "was scaled or turned when it was read, so its pixels are not those of the saved JPEG"
    if turn != 1:
        return "was turned upright when it was read (the picture says so), so its pixels are not laid on the grid of the saved JPEG"
    return None


def jpeg_history(case: Case, doc: Document, ctx: Ctx) -> list[Finding]:
    out: list[Finding] = []
    issues: dict[str, list[int]] = {}  # the reason a page was not examined: the pages it applies to
    for pg in doc.pages:
        if pg.read_mode != "ocr":
            continue
        if why := _why_not(doc, pg, ctx):
            issues.setdefault(why, []).append(pg.n)
            continue
        with Image.open(ctx.cd.root / pg.image_path) as im:
            r = ela_regions(np.asarray(im.convert("L")))
        if not r.regions:
            continue
        shown = r.regions[:LISTED]
        more = f" ({LISTED} of them listed)" if len(r.regions) > LISTED else ""
        noun, verb, poss, obj = ("region", "does", "its", "the region") if len(r.regions) == 1 else ("regions", "do", "their", "them")
        ev = [Evidence(doc=doc.id, page=pg.n, box=g.box,
                       note=f"saving again at quality {r.earlier} changes its ink by {g.error:.1f} grey levels on average, against {r.median:.1f} for the page's median cell")
              for g in shown]
        out.append(Finding(
            fclass="observation", detector=DETECTOR, family="visual", title=f"Part of the page has no trace of the page's earlier JPEG save (page {pg.n})",
            detail=f"Page {pg.n} was last saved as a JPEG at about quality {r.final}, and most of its ink still carries a trace of an earlier save: "
                   f"saving it again at about quality {r.earlier} changes it less than at the qualities beside it (by a factor of {r.dip:.1f}). "
                   f"That is where the trace shows, which is not always the quality of the earlier save. "
                   f"{len(r.regions)} compact {noun}{more} {verb} not share that trace: saving again at {r.earlier} changes {poss} ink "
                   f"by at least {MIN_RATIO:g} times the page's median ({r.median:.1f} grey levels) and by more than {Z:g} robust standard "
                   f"deviations, and saving at the qualities either side of it alters {obj} as much ({poss} own dip is under {MAX_DIP:g}, against "
                   f"{r.dip:.1f} for the page as a whole). Qualities were tried in steps of {QUALITIES[1] - QUALITIES[0]}, so the figures are "
                   f"approximate.", evidence=ev))
    if issues:  # one clause for each reason, with the first page it applies to and how many more: a long scanned file stays short
        clauses = [f"page {ns[0]} {why}" + (f" (and {len(ns) - 1} more page{'s' if len(ns) > 2 else ''} for the same reason)" if len(ns) > 1 else "")
                   for why, ns in issues.items()]
        out.append(limitation(DETECTOR, "Compression history not examined", "The JPEG history of a page was not examined: " + "; ".join(clauses) + ".",
                              [doc_evidence(doc.id, "scanned pages")]))
    return out
