"""Signature comparison (design 8, C4). Documents of one case that carry a drawn signature should carry the same hand. Where a
signature is, is data: the spec of each document type lists the captions printed under it. The area above the caption, sized by the
caption's word height so that it follows the resolution of the page, is turned into a mask of ink; the mask is straightened by the
turn of its page, cut to its bounding box and scaled to a fixed canvas. Two canvases differ when more than `signature_dist` percent of
the ink of the one lies farther than _REACH px from the ink of the other, at the best slide of one over the other. That compares
shapes. It does not say who signed, one person's signatures vary from signing to signing, and the limit was fitted on synthetic hands
only (docs/spike.md, Task 25). A mismatch is an inconsistency for a reviewer to look at; a signature that could not be found or
read is a limitation and never a pass."""
from dataclasses import dataclass
from itertools import combinations, product

import cv2
import numpy as np
from PIL import Image

from ..findings import doc_evidence, limitation
from ..model import Case, Document, Evidence, Finding, Page, Word
from ..pipeline import Ctx
from ..understand.layout import find_phrase, lines_of, union
from ..understand.specs import load_specs
from .scan_layout import MAX_TURN, MIN_WORDS, page_turn

DETECTOR = "signature"
_CANVAS = (192, 64)        # (width, height) in px that a cut signature is scaled to
_REACH = 6                 # px on the canvas: ink farther than this from the other signature's ink is unmatched
_SHIFT = 4                 # px on the canvas: one signature may slide this far over the other, either way and in each direction
_SPECK = 12                # px: smaller marks are noise, not ink
_STRAY = 0.1               # a piece of ink under this share of the largest piece, outside the box of the bigger ones, is a stray mark
_AREA = (-0.8, 17.0, -6.6)  # left, right and top of the area searched, in caption word heights from the caption's left edge and top; its bottom is the caption's top
_MAX_SHARE = 0.15          # ink share of the area above which it is printed matter and not a signature (ponytail: a heavy signature in a small area fails here)


@dataclass
class _Sig:
    doc: Document
    page: int
    box: tuple[float, float, float, float]  # the ink, in the pixels of the page image
    canvas: np.ndarray                       # the cut and scaled ink, padded by _SHIFT so that it can slide


def label(d: Document) -> str:
    return f"{d.id} ({d.doc_type.replace('_', ' ')})"


def ink(gray: np.ndarray) -> np.ndarray:
    """Marks that are darker than the paper by more than 50 grey levels, without the specks (pieces under 12 px). The paper is the
    median of the 31 px around a pixel, so it follows the lighting; where that median is itself more than 50 levels darker than the
    median of the whole area, the 31 px lie inside a mark wider than 15 px, and the paper is the median of the area."""
    local, area = cv2.medianBlur(gray, 31).astype(np.int16), int(np.median(gray))
    paper = np.where(local < area - 50, area, local)
    marks = (gray.astype(np.int16) < paper - 50).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(marks, connectivity=8)
    return np.isin(lab, [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= _SPECK])


def strays_out(mask: np.ndarray) -> np.ndarray:
    """The mask without its stray marks: pieces under a tenth of the largest piece that stick out of the box of the bigger ones, and
    would stretch the box a mark is cut to. Call it after the check that the area is not mostly ink: a crowd of pieces is printed
    matter, and must not be thinned to a mark first."""
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if n < 2:
        return mask
    area, x0, y0 = st[1:, cv2.CC_STAT_AREA], st[1:, cv2.CC_STAT_LEFT], st[1:, cv2.CC_STAT_TOP]
    x1, y1 = x0 + st[1:, cv2.CC_STAT_WIDTH], y0 + st[1:, cv2.CC_STAT_HEIGHT]
    big = area >= _STRAY * area.max()
    within = (x0 >= x0[big].min()) & (y0 >= y0[big].min()) & (x1 <= x1[big].max()) & (y1 <= y1[big].max())
    return np.isin(lab, np.flatnonzero(big | within) + 1)


def canvas(mask: np.ndarray, turn: float, size: tuple[int, int], shift: int, rot: float = 0.0) -> np.ndarray:
    """The ink turned back by the turn of its page (anticlockwise is positive) and by `rot` degrees more, cut to its box and scaled
    to `size` (width, height), padded by `shift` px so that it can slide."""
    m = np.pad(mask.astype(np.float32), 60)
    ang = -(turn + rot)
    if ang:
        r = cv2.getRotationMatrix2D((m.shape[1] / 2, m.shape[0] / 2), ang, 1.0)
        m = cv2.warpAffine(m, r, (m.shape[1], m.shape[0]), flags=cv2.INTER_LINEAR)
    ys, xs = np.nonzero(m > 0.5)
    crop = (m[ys.min():ys.max() + 1, xs.min():xs.max() + 1] > 0.5).astype(np.float32)
    return np.pad(cv2.resize(crop, size, interpolation=cv2.INTER_AREA) > 0.3, shift)


def distance(a: np.ndarray, b: np.ndarray, reach: float, shift: int) -> float:
    """Percent of the ink of the one that lies farther than `reach` px from the ink of the other (the larger of the two shares), at the
    slide of one over the other, within `shift` px, where it is smallest."""
    pa, pb = np.argwhere(a), np.argwhere(b)
    da, db = (cv2.distanceTransform((~c).astype(np.uint8), cv2.DIST_L2, 3) for c in (a, b))
    return min(100 * max((db[pa[:, 0] + dy, pa[:, 1] + dx] > reach).mean(), (da[pb[:, 0] - dy, pb[:, 1] - dx] > reach).mean())
               for dy, dx in product(range(-shift, shift + 1), repeat=2))


def find_caption(doc: Document, captions: list[str], what: str, ctx: Ctx) -> tuple[Page, list[Word]] | str:
    """The page and the words of the caption of `what` (the best match of any wording in `captions`, on a page that is not poor;
    of equals the lowest on the latest page), or the reason there is none."""
    poor = [p.n for p in doc.pages if p.quality_class == "poor"]
    best = None
    for pg in doc.pages:
        if pg.quality_class == "poor":
            continue
        for line in lines_of(pg):
            for phrase in captions:
                hit = find_phrase(line.words, phrase, ctx.th.label_sim)
                if hit and (best is None or (hit[2], pg.n, line.box[1]) > best[0]):
                    best = ((hit[2], pg.n, line.box[1]), pg, line.words[hit[0]:hit[0] + hit[1]])
    if best is None:
        return f"page {poor[0]} is of poor quality (class poor), so its {what} was not compared" if poor else f"the caption of the {what} was not found"
    return best[1], best[2]


def page_image(pg: Page, ctx: Ctx) -> tuple[np.ndarray, float] | str:
    """The grey image of the page and the turn of the page in degrees (0 for a text-layer page), or the reason the page cannot be
    straightened."""
    turn = 0.0
    if pg.read_mode == "ocr":
        if len(pg.words) < MIN_WORDS:
            return f"page {pg.n} has {len(pg.words)} words, fewer than the {MIN_WORDS} needed to find how far it is turned"
        turn = page_turn(pg.words, pg.width, pg.height)
        if abs(turn) > MAX_TURN:
            return f"page {pg.n} is turned by {turn:+.1f} degrees, more than the {MAX_TURN:g} that is compared, so it was not straightened"
    with Image.open(ctx.cd.root / pg.image_path) as im:
        return np.asarray(im.convert("L")), turn


def _locate(doc: Document, captions: list[str], ctx: Ctx) -> _Sig | str:
    """The signature of a document, or the reason it could not be compared."""
    got = find_caption(doc, captions, "signature", ctx)
    if isinstance(got, str):
        return got
    pg, words = got
    box = union(w.box for w in words)
    u = float(np.median([w.box[3] - w.box[1] for w in words]))
    seen = page_image(pg, ctx)
    if isinstance(seen, str):
        return seen
    gray, turn = seen
    left, right, top = _AREA
    x0, x1 = max(int(box[0] + left * u), 0), min(int(box[0] + right * u), gray.shape[1])
    y0, y1 = max(int(box[1] + top * u), 0), min(int(box[1]), gray.shape[0])
    if x1 - x0 < 8 * u or y1 - y0 < 4 * u:
        return f"too little of page {pg.n} lies above the caption to hold a signature"
    mask = ink(gray[y0:y1, x0:x1])
    if mask.sum() > _MAX_SHARE * mask.size:
        return f"the area above the caption on page {pg.n} is mostly ink, which a signature is not"
    mask = strays_out(mask)
    ys, xs = np.nonzero(mask)
    if ys.size < 0.25 * u * u:
        return f"no ink was found above the caption on page {pg.n}"
    if xs.min() == 0 or xs.max() == mask.shape[1] - 1 or ys.min() == 0:
        return f"ink on page {pg.n} reaches the edge of the area above the caption, so the signature may be cut off"
    return _Sig(doc, pg.n, (float(x0 + xs.min()), float(y0 + ys.min()), float(x0 + xs.max() + 1), float(y0 + ys.max() + 1)), canvas(mask, turn, _CANVAS, _SHIFT))


def compare_signatures(case: Case, ctx: Ctx) -> list[Finding]:
    """Draft findings for the signatures of the case: every pair of documents that carry one is compared and logged; a pair that
    differs is an inconsistency. When two or more documents were meant to carry a signature and not all could be compared, one
    limitation says which and why. One signed document alone has nothing to be compared with, and says nothing."""
    th = ctx.th
    specs = load_specs()
    found: list[_Sig] = []
    issues: list[tuple[Document, str]] = []
    asked = 0
    for doc in case.documents:
        spec = specs.get(doc.doc_type)
        if spec is None or not spec.signature:
            continue
        asked += 1
        got = _locate(doc, spec.signature, ctx)
        if isinstance(got, str):
            issues.append((doc, got))
        else:
            found.append(got)
    out: list[Finding] = []
    for a, b in combinations(found, 2):
        dist = distance(a.canvas, b.canvas, _REACH, _SHIFT)
        differs = bool(dist > th.signature_dist)
        ctx.audit.append("system", "signature_compared", {"docs": [a.doc.id, b.doc.id], "pages": [a.page, b.page], "distance": round(dist, 2),
                                                          "limit": th.signature_dist, "differs": differs})
        if differs:
            out.append(Finding(
                fclass="inconsistency", detector=DETECTOR, family="cross_document",
                title=f"Signature differs between {label(a.doc)} and {label(b.doc)}",
                detail=f"The signature above the caption on page {a.page} of {label(a.doc)} and the one on page {b.page} of {label(b.doc)} are not "
                       f"the same shape. Each was straightened by the turn of its page, cut to its ink and scaled to {_CANVAS[0]} x {_CANVAS[1]} px; "
                       f"{dist:.1f} % of the ink of the one then lies more than {_REACH} px from the ink of the other, at the best placement of one "
                       f"over the other within {_SHIFT} px. The limit is {th.signature_dist:g} %. This compares shapes only. It does not say who "
                       f"signed: one person's signatures vary from signing to signing, a scan can distort a stroke, and the limit was set on "
                       f"synthetic signatures.",
                evidence=[Evidence(doc=s.doc.id, page=s.page, box=s.box, note=f"signature on page {s.page}") for s in (a, b)]))
    if asked >= 2 and issues:
        out.append(limitation(DETECTOR, "Signatures only partly compared",
                              "Signatures were not compared everywhere: " + "; ".join(f"{label(d)}: {why}" for d, why in issues) + ".",
                              [doc_evidence(d.id, "signature not compared") for d, _ in issues]))
    return out
