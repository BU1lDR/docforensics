"""Issuer marks (design 8, C5). Documents of one issuer should carry the same logo, right of the issuer's name, and the same stamp,
above a caption. Which documents are of one issuer is read from the line that names it, the topmost line of page 1 that reads as a
name among those about as tall (within 15 %) as the tallest: documents whose lines read alike (`text_sim`) are of one. Where a mark
is, is data: the spec of each document type says whether the document carries a logo and lists the captions printed under its
stamp. A window, sized by a word height so that it follows the resolution of the page, is turned into a mask of ink, straightened by the turn of its page, cut to its bounding box and scaled to a
fixed canvas. Two canvases differ when more than `logo_dist` or `stamp_dist` percent of the ink of the one lies farther than _REACH px
from the ink of the other, at the best slide of one over the other; a stamp is pressed by hand, so for stamps also at the best turn of
one of them within 8 degrees. That compares shapes. It does not say who issued the document, and the limits were fitted on synthetic
marks only: two of the six designs drawn for them, both logos of one motif, are not told apart at any limit (docs/spike.md, Task 26).
A mismatch is an inconsistency for a reviewer to look at; a mark that could not be found or read is a limitation and never a pass."""
from dataclasses import dataclass
from itertools import combinations

import cv2
import numpy as np

from ..findings import doc_evidence, limitation
from ..model import Case, Document, Evidence, Finding
from ..pipeline import Ctx
from ..understand.layout import Line, issuer_line, lines_of, similar, text_of, union
from ..understand.specs import TypeSpec, load_specs
from .signature import canvas, distance, find_caption, ink, label, page_image, strays_out

DETECTOR = "mark"
_SIZE = (128, 128)  # (width, height) in px that a cut mark is scaled to
_REACH = 3          # px on the canvas: ink farther than this from the other mark's ink is unmatched
_SHIFT = 3          # px on the canvas: one mark may slide this far over the other, either way and in each direction
_TURNS = {"logo": (0.0,), "stamp": tuple(float(r) for r in range(-8, 9, 2))}  # degrees: how far one of two marks is turned to its best fit
# The window searched, in word heights: left, right, top and bottom of it from the anchor. The anchor of a logo is the right end of the
# issuer line at its middle; the anchor of a stamp is the left edge and the top of its caption, so the window lies above the caption.
_AREA = {"logo": (0.2, 4.5, -1.5, 1.5), "stamp": (-1.2, 10.0, -10.5, -0.1)}
_MAX_SHARE = 0.3    # ink share of the window above which it is printed matter and not a mark (ponytail: a mark that fills its window fails here)
_MIN_INK = 0.25     # ink, in squares of a word height, below which there is no mark: the genuine marks have 0.63 or more
_ERASE = 0.1      # word heights: how far past the box of a word of text its pixels are erased from a logo window
_TOUCH = 3        # px: erased text this close to the ink of a logo touches it, and a line of text ending this close to the logo's right edge ends inside it


@dataclass
class _Mark:
    doc: Document
    page: int
    box: tuple[float, float, float, float]  # the ink, in the pixels of the page image
    ink: np.ndarray                          # the mask of ink in the window
    turn: float                              # degrees the page is turned by


def _locate(kind: str, doc: Document, spec: TypeSpec, line: Line, ctx: Ctx) -> _Mark | str:
    """The mark of this kind on a document, or the reason it could not be compared."""
    if kind == "logo":
        pg, u = doc.pages[0], line.height
        anchor = (max(w.box[2] for w in line.words), (line.box[1] + line.box[3]) / 2)
    else:
        got = find_caption(doc, spec.stamp, kind, ctx)
        if isinstance(got, str):
            return got
        pg, words = got
        box = union(w.box for w in words)
        u, anchor = float(np.median([w.box[3] - w.box[1] for w in words])), box[:2]
    seen = page_image(pg, ctx)
    if isinstance(seen, str):
        return seen
    gray, turn = seen
    left, right, top, bottom = _AREA[kind]
    x0, x1 = max(int(anchor[0] + left * u), 0), min(int(anchor[0] + right * u), gray.shape[1])
    y0, y1 = max(int(anchor[1] + top * u), 0), min(int(anchor[1] + bottom * u), gray.shape[0])
    if x1 - x0 < 0.5 * (right - left) * u or y1 - y0 < 0.5 * (bottom - top) * u:
        return f"too little of page {pg.n} lies around the {kind} to hold it"
    mask = ink(gray[y0:y1, x0:x1])
    text, lines = np.zeros(mask.shape, bool), []  # the pixels of the words of other lines that reach into a logo window, per line
    if kind == "logo":  # under a short name the line beneath it runs on into the window: its words are text and not the logo
        pad = int(_ERASE * u)
        for other in lines_of(pg):
            if other.box != line.box and other.box[0] < anchor[0]:
                t = np.zeros(mask.shape, bool)
                for w in other.words:
                    bx0, by0, bx1, by1 = (int(v) for v in w.box)
                    t[max(by0 - y0 - pad, 0):max(by1 - y0 + pad, 0), max(bx0 - x0 - pad, 0):max(bx1 - x0 + pad, 0)] = True
                text |= t
                lines.append((t, int(other.box[2]) + pad - x0))
    erased, mask = mask & text, mask & ~text
    if mask.sum() > _MAX_SHARE * mask.size:
        return f"the area for the {kind} on page {pg.n} is mostly ink, which a {kind} is not"
    mask = strays_out(mask)
    ys, xs = np.nonzero(mask)
    if ys.size < _MIN_INK * u * u:
        return f"no ink was found where the {kind} should be on page {pg.n}"
    near = cv2.dilate(mask.astype(np.uint8), np.ones((2 * _TOUCH + 1,) * 2, np.uint8)).astype(bool)
    if any((erased & t & near).any() and end < xs.max() + _TOUCH for t, end in lines):  # a line that stops inside the logo cuts it differently in each document
        return f"text of another line ends inside the {kind} on page {pg.n}, so what is the {kind} and what is the text cannot be told apart"
    if xs.min() == 0 or xs.max() == mask.shape[1] - 1 or ys.min() == 0 or ys.max() == mask.shape[0] - 1:
        return f"ink on page {pg.n} reaches the edge of the area for the {kind}, so the {kind} may be cut off"
    return _Mark(doc, pg.n, (float(x0 + xs.min()), float(y0 + ys.min()), float(x0 + xs.max() + 1), float(y0 + ys.max() + 1)), mask, turn)


def _distance(kind: str, a: _Mark, b: _Mark) -> float:
    ca = canvas(a.ink, a.turn, _SIZE, _SHIFT)
    return min(distance(ca, canvas(b.ink, b.turn, _SIZE, _SHIFT, rot), _REACH, _SHIFT) for rot in _TURNS[kind])


def issuer_groups(case: Case, ctx: Ctx) -> tuple[list[Document], list[list[tuple[Document, Line]]], list[tuple[Document, str, str]]]:
    """The documents that may carry a logo or a stamp, those of them grouped by the line that names their issuer (each with its line),
    and, for the ones that could not be grouped, (document, what was not compared, why)."""
    specs = load_specs()
    candidates = [d for d in case.documents if (s := specs.get(d.doc_type)) and (s.logo or s.stamp)]
    issues: list[tuple[Document, str, str]] = []
    groups: list[list[tuple[Document, Line]]] = []
    for doc in candidates:
        pg = doc.pages[0]
        if pg.quality_class == "poor":
            issues.append((doc, "marks", "page 1 is of poor quality (class poor), so its marks were not compared"))
            continue
        line = issuer_line(lines_of(pg))
        if line is None:
            issues.append((doc, "marks", "no issuer line (a line of three letters or digits at least) was found on page 1, so its marks "
                                         "could not be grouped with those of one issuer"))
            continue
        for g in groups:
            if similar(text_of(g[0][1].words), text_of(line.words), ctx.th.text_sim):
                g.append((doc, line))
                break
        else:
            groups.append([(doc, line)])
    return candidates, groups, issues


def compare_marks(case: Case, ctx: Ctx) -> list[Finding]:
    """Draft findings for the logos and stamps of the case: the documents are grouped by the line that names their issuer, every pair
    of one group that carries a mark of a kind is compared and logged, and a pair that differs is an inconsistency. When two or more
    documents were meant to carry a mark and not all could be compared, one limitation says which and why. A document that is the
    only one of its issuer has nothing to be compared with, and says nothing."""
    th, specs = ctx.th, load_specs()
    candidates, groups, issues = issuer_groups(case, ctx)
    out: list[Finding] = []
    paired: set[str] = set()  # the kinds of which two documents of one issuer were compared
    for g in groups:
        for kind in ("logo", "stamp"):
            asking = [(d, ln) for d, ln in g if getattr(specs[d.doc_type], kind)]
            if len(asking) < 2:
                continue
            paired.add(kind)
            found: list[_Mark] = []
            for d, ln in asking:
                got = _locate(kind, d, specs[d.doc_type], ln, ctx)
                if isinstance(got, str):
                    issues.append((d, kind, got))
                else:
                    found.append(got)
            limit = getattr(th, f"{kind}_dist")
            for a, b in combinations(found, 2):
                dist = _distance(kind, a, b)
                differs = bool(dist > limit)
                ctx.audit.append("system", "mark_compared", {"kind": kind, "docs": [a.doc.id, b.doc.id], "pages": [a.page, b.page],
                                                              "distance": round(dist, 2), "limit": limit, "differs": differs})
                if differs:
                    turned = f", the second turned to its best fit within {max(_TURNS[kind]):g} degrees either way" if kind == "stamp" else ""
                    out.append(Finding(
                        fclass="inconsistency", detector=DETECTOR, family="cross_document",
                        title=f"{kind.capitalize()} differs between {label(a.doc)} and {label(b.doc)}",
                        detail=f"The {kind} on page {a.page} of {label(a.doc)} and the one on page {b.page} of {label(b.doc)} are not the same "
                               f"shape. Each was straightened by the turn of its page, cut to its ink and scaled to {_SIZE[0]} x {_SIZE[1]} px; "
                               f"{dist:.1f} % of the ink of the one then lies more than {_REACH} px from the ink of the other, at the best "
                               f"placement of one over the other within {_SHIFT} px{turned}. The limit is {limit:g} %. This compares shapes "
                               f"only. It does not say who issued either document: a {kind} varies from impression to impression, a scan can "
                               f"blur a fine {kind}, and the limit was set on synthetic marks.",
                        evidence=[Evidence(doc=m.doc.id, page=m.page, box=m.box, note=f"{kind} on page {m.page}") for m in (a, b)]))
    for kind in ("logo", "stamp"):  # two documents carry this mark but none shares its issuer line with another: nothing was compared
        asking = [(d, ln) for g in groups for d, ln in g if getattr(specs[d.doc_type], kind)]
        if len(asking) >= 2 and kind not in paired:
            issues += [(d, kind, f'no other document has an issuer line like "{text_of(ln.words)}", so it was not compared') for d, ln in asking]
    if len(candidates) >= 2 and issues:
        out.append(limitation(DETECTOR, "Issuer marks only partly compared",
                              "Marks were not compared everywhere: " + "; ".join(f"{label(d)}, {what}: {why}" for d, what, why in issues) + ".",
                              [doc_evidence(d.id, f"{what} not compared") for d, what, _ in issues]))
    return out
