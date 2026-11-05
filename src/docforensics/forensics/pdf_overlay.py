"""Covered and hidden text, and pictures placed over text (design 7.5, D2 and D5). A PDF page is a list of drawing operations in
the order they were made, and PyMuPDF numbers text runs and filled shapes in one sequence. Text that is still in the file but
lies under a shape or picture drawn after it is what a cover-and-retype leaves behind; text that cannot be seen (invisible,
tiny, off the page) is reported as well. Every finding states what was measured, not why."""
import pymupdf

from ..config import Thresholds
from ..findings import doc_evidence, limitation, quote
from ..model import Box, Case, Document, Evidence, Finding, Page
from ..pipeline import Ctx

DETECTOR = "pdf_overlay"
LISTED = 12  # runs of text named in one finding; more are counted
SHOWN = (0, 1, 2)  # text render modes that paint something: fill, stroke, both
_COVERED = 0.5  # a character counts as covered when at least this share of its box lies under the shape
_OPAQUE = 0.99


def _text(chars) -> str:
    return "".join(chr(c[0]) for c in chars)


def _share(inner, outer) -> float:
    """The share of the box `inner` that lies inside the box `outer`."""
    w = min(inner[2], outer[2]) - max(inner[0], outer[0])
    h = min(inner[3], outer[3]) - max(inner[1], outer[1])
    area = (inner[2] - inner[0]) * (inner[3] - inner[1])
    return w * h / area if w > 0 and h > 0 and area > 0 else 0.0


def _px(box, scale: float) -> Box:
    return tuple(round(float(v) * scale, 2) for v in box)  # type: ignore[return-value]


def _under(spans: list[dict], before: int, area) -> list[tuple[str, tuple]]:
    """The text of visible runs drawn before operation `before` that lies under `area`: (text, box) per run, with the characters
    that are at least half under it, from the first to the last."""
    found = []
    for s in spans:
        if s["seqno"] < before and s["type"] in SHOWN:
            hit = [i for i, c in enumerate(s["chars"]) if chr(c[0]).strip() and _share(c[3], area) >= _COVERED]
            if hit:
                chars = s["chars"][hit[0]:hit[-1] + 1]
                found.append((_text(chars), (min(c[3][0] for c in chars), min(c[3][1] for c in chars),
                                             max(c[3][2] for c in chars), max(c[3][3] for c in chars))))
    return found


def _colour(c) -> str:
    return "#%02x%02x%02x" % tuple(round(v * 255) for v in c) if c and len(c) == 3 else str(tuple(round(v, 2) for v in c or ()))


def _turned(mu: pymupdf.Page, box) -> pymupdf.Rect:
    """A box on the page as it was drawn, as the reader and the viewer show the page: turned by its /Rotate."""
    return pymupdf.Rect(box) * mu.rotation_matrix


def _evidence(doc: Document, pg: Page, mu: pymupdf.Page, box, note: str, value: str | None = None) -> Evidence:
    return Evidence(doc=doc.id, page=pg.n, box=_px(_turned(mu, box), pg.dpi / 72), note=note, value=None if value is None else quote(value))


def _shapes(mu: pymupdf.Page) -> list[tuple[int, tuple, tuple]]:
    """Opaque filled rectangles as (operation number, box, fill colour)."""
    return [(d["seqno"], tuple(d["rect"]), d["fill"]) for d in mu.get_drawings()
            if d["fill"] is not None and d["type"] in ("f", "fs") and (d.get("fill_opacity") is None or d["fill_opacity"] >= _OPAQUE)
            and len(d["items"]) == 1 and d["items"][0][0] == "re"]


def _covers(doc: Document, pg: Page, spans: list[dict], mu: pymupdf.Page) -> list[Finding]:
    out = []
    for k, rect, fill in _shapes(mu):
        old = _under(spans, k, rect)
        if not old:
            continue
        new = [s for s in spans if s["seqno"] > k and s["type"] in SHOWN and _text(s["chars"]).strip() and _share(s["bbox"], rect) >= _COVERED]
        was = quote(" ".join(t for t, _ in old))
        size = f"{rect[2] - rect[0]:.0f} x {rect[3] - rect[1]:.0f} pt, fill {_colour(fill)}"
        ev = [_evidence(doc, pg, mu, s["bbox"], "text drawn over the shape", _text(s["chars"]).strip()) for s in new[:LISTED]]
        ev += [_evidence(doc, pg, mu, box, "text drawn under the shape, still in the file", t) for t, box in old[:LISTED]]
        ev.append(_evidence(doc, pg, mu, rect, "the filled shape"))
        rule = f"Text counts as covered when at least {_COVERED:.0%} of a character's box lies under a shape drawn after it."
        if new:
            now = quote(" ".join(_text(s["chars"]).strip() for s in new))
            out.append(Finding(fclass="observation", detector=DETECTOR, family="visual", title=f"Text written over a filled shape that hides other text (page {pg.n})",
                               detail=f'On page {pg.n} a filled shape ({size}) is drawn over the text "{was}", which is still in the file. '
                                      f'The text "{now}" is drawn on top of the shape. {rule}', evidence=ev))
        else:
            out.append(Finding(fclass="observation", detector=DETECTOR, family="visual", title=f"Text lies under a filled shape (page {pg.n})",
                               detail=f'On page {pg.n} the text "{was}" is still in the file but is drawn under a filled shape ({size}). '
                                      f'No text is drawn over the shape. {rule}', evidence=ev))
    return out


def _pictures(doc: Document, pg: Page, spans: list[dict], mu: pymupdf.Page, th: Thresholds) -> tuple[list[Finding], bool]:
    """Pictures smaller than image_max_page_fraction of the page, and whether the page is mostly one picture (a scan)."""
    out, whole = [], False
    page_area = mu.rect.width * mu.rect.height
    for k, (name, rect) in enumerate(mu.get_bboxlog()):
        if "image" not in name and "imgmask" not in name:
            continue
        share = (rect[2] - rect[0]) * (rect[3] - rect[1]) / page_area
        if share >= th.image_max_page_fraction:
            whole = True
            continue
        old = _under(spans, k, tuple(rect))
        size = f"{rect[2] - rect[0]:.0f} x {rect[3] - rect[1]:.0f} pt, {share:.1%} of the page"
        rule = f"Pictures covering less than {th.image_max_page_fraction:.0%} of a text page are reported."
        ev = [_evidence(doc, pg, mu, rect, "the picture")] + [_evidence(doc, pg, mu, box, "text drawn under the picture, still in the file", t) for t, box in old[:LISTED]]
        if old:
            out.append(Finding(fclass="observation", detector=DETECTOR, family="visual", title=f"Picture placed over text (page {pg.n})",
                               detail=f'On page {pg.n} a picture ({size}) is drawn over the text "{quote(" ".join(t for t, _ in old))}", '
                                      f"which is still in the file. {rule}", evidence=ev))
        else:
            out.append(Finding(fclass="observation", detector=DETECTOR, family="visual", title=f"Picture on a page of text (page {pg.n})",
                               detail=f"On page {pg.n}, which has a text layer, a picture ({size}) is drawn. It does not lie over any text. "
                                      f"A logo, stamp or signature placed as a picture is reported the same way. {rule}", evidence=ev))
    return out, whole


def _hidden(doc: Document, pg: Page, spans: list[dict], mu: pymupdf.Page, th: Thresholds, scan_layer: bool) -> list[Finding]:
    kinds: dict[str, list[dict]] = {"invisible": [], "tiny": [], "off the page": []}
    for s in spans:
        if not _text(s["chars"]).strip():
            continue
        if s["type"] == 3:
            if not scan_layer:  # invisible text on a page that is one picture is the text layer of a scan
                kinds["invisible"].append(s)
        elif not mu.rect.intersects(_turned(mu, s["bbox"])):  # mu.rect is the page as shown, so the run is turned as well
            kinds["off the page"].append(s)
        elif s["type"] in SHOWN and s["size"] < th.tiny_text_pt:
            kinds["tiny"].append(s)
    out = []
    for kind, found in kinds.items():
        if not found:
            continue
        words = quote('"; "'.join(_text(s["chars"]).strip() for s in found[:LISTED]))
        more = f" and {len(found) - LISTED} more" if len(found) > LISTED else ""
        how = {"invisible": "stored with the invisible text setting (render mode 3), so it is in the file but is not shown",
               "tiny": f"set smaller than the {th.tiny_text_pt:g} pt that can be read by eye (smallest here: {min(s['size'] for s in found):g} pt)",
               "off the page": f"placed outside the {mu.rect.width:.0f} x {mu.rect.height:.0f} pt page"}[kind]
        title = {"invisible": "Invisible text", "tiny": "Tiny text", "off the page": "Text placed off the page"}[kind]
        if kind == "off the page":
            ev = [Evidence(doc=doc.id, page=0, box=(0.0, 0.0, 0.0, 0.0),
                           note=f"page {pg.n}, outside the page, at x={_turned(mu, s['bbox']).x0:.0f} pt, y={_turned(mu, s['bbox']).y0:.0f} pt",
                           value=quote(_text(s["chars"]).strip())) for s in found[:LISTED]]
        else:
            ev = [_evidence(doc, pg, mu, s["bbox"], f"{kind} text", _text(s["chars"]).strip()) for s in found[:LISTED]]
        out.append(Finding(fclass="observation", detector=DETECTOR, family="visual", title=f"{title} (page {pg.n})",
                           detail=f'Page {pg.n} has {len(found)} text run(s) {how}: "{words}"{more}.', evidence=ev))
    return out


def covered_or_hidden_text(case: Case, doc: Document, ctx: Ctx) -> list[Finding]:
    th = ctx.th
    out: list[Finding] = []
    issues: list[str] = []
    with pymupdf.open(stream=(ctx.cd.root / doc.stored_path).read_bytes(), filetype="pdf") as pdf:
        for pg in doc.pages:
            if pg.read_mode != "text-layer" or pg.n > pdf.page_count:
                continue
            mu = pdf[pg.n - 1]
            drawn = len(mu.get_bboxlog())
            if drawn > th.max_page_objects:
                issues.append(f"page {pg.n} draws {drawn} objects, over the {th.max_page_objects} examined")
                continue
            spans = [s for s in mu.get_texttrace() if s["chars"]]
            pictures, scan_layer = _pictures(doc, pg, spans, mu, th)
            out += _covers(doc, pg, spans, mu) + pictures + _hidden(doc, pg, spans, mu, th, scan_layer)
    if issues:
        out.append(limitation(DETECTOR, "Covered and hidden text only partly examined",
                              "Some pages were not examined for text under shapes or pictures or for hidden text: " + "; ".join(issues[:10]) + ".",
                              [doc_evidence(doc.id, "page content")]))
    return out
