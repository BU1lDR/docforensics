"""Fonts of figures and dates (design 7.5, D3). Text written over a covered figure in a face that only looks like the page's own
(Arial for Helvetica) differs in the name the file gives the font, though not to the eye. Values that are numbers or dates are
compared with the other such values in their column and on their line; one whose font, size or colour differs from what most of
the group share is reported with the measured values. Only values that stand in a text run of their own can be compared."""
import re
from collections import Counter

import pymupdf

from ..findings import doc_evidence, limitation
from ..model import Case, Document, Finding
from ..pipeline import Ctx
from .pdf_overlay import SHOWN, _colour, _evidence, _text

DETECTOR = "pdf_fonts"
LISTED = 12  # findings made for one page; more are counted
_VALUE = re.compile(r"(?:₹|Rs\.?|INR)?\s*[\d,./:\- ]*\d[\d,./:\- ]*(?:Cr|Dr)?", re.I)
_MIN_COLUMN, _MIN_LINE = 4, 3  # values needed for a group to say what is usual in it
_SHARE = 0.6  # the share of a group that must agree on a font, size or colour for that to be what is usual
_LINE_PT = 3.0  # values whose middles are this close (points) stand on one line
_ATTR = ("font", "size", "colour")


def family(name: str) -> str:
    """The font's family as the file spells it, without the subset prefix, the style and the suffixes MT and PS."""
    base = re.split(r"[-,]", name.split("+")[-1].lower())[0]
    return re.sub(r"(ps)?(mt)?$", "", base)


def _overlap(a, b) -> float:
    narrow = min(a[2] - a[0], b[2] - b[0])
    return (min(a[2], b[2]) - max(a[0], b[0])) / narrow if narrow > 0 else 0.0


def _groups(values: list[dict]) -> list[tuple[str, list[int]]]:
    seen, out = set(), []
    for s in values:
        mid = (s["bbox"][1] + s["bbox"][3]) / 2
        for kind, need, near in (("column", _MIN_COLUMN, lambda t: _overlap(s["bbox"], t["bbox"]) >= 0.5),
                                 ("line", _MIN_LINE, lambda t: abs((t["bbox"][1] + t["bbox"][3]) / 2 - mid) <= _LINE_PT)):
            members = tuple(j for j, t in enumerate(values) if near(t))
            if len(members) >= need and (kind, members) not in seen:
                seen.add((kind, members))
                out.append((kind, list(members)))
    return out


def _unusual(values: list[dict], kind: str, members: list[int], th) -> dict[int, dict[str, str]]:
    """For each member that differs from what most of the group share, what differs, as a sentence for each attribute."""
    keys = {"font": lambda s: s["family"], "size": lambda s: round(s["size"], 1), "colour": lambda s: s["colour"]}
    shown = {"font": lambda s: s["font"], "size": lambda s: f"{s['size']:g} pt", "colour": lambda s: s["colour"]}
    out: dict[int, dict[str, str]] = {}
    for attr in _ATTR:
        usual, n = Counter(keys[attr](values[j]) for j in members).most_common(1)[0]
        if n / len(members) < _SHARE:
            continue
        ref = next(values[j] for j in members if keys[attr](values[j]) == usual)
        for j in members:
            own = values[j]
            differs = abs(own["size"] - ref["size"]) > th.font_size_delta_pt if attr == "size" else keys[attr](own) != usual
            if differs:
                out.setdefault(j, {}).setdefault(attr, f"{attr} {shown[attr](own)} where {n} of the {len(members)} values in its {kind} "
                                                       f"have {shown[attr](ref)}")
    return out


def font_outliers(case: Case, doc: Document, ctx: Ctx) -> list[Finding]:
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
            values = [{"text": _text(s["chars"]).strip(), "font": s["font"], "family": family(s["font"]), "size": s["size"],
                       "colour": _colour(s["color"]), "bbox": s["bbox"]}
                      for s in mu.get_texttrace() if s["chars"] and s["type"] in SHOWN and _VALUE.fullmatch(_text(s["chars"]).strip())]
            notes: dict[int, dict[str, str]] = {}
            for kind, members in _groups(values):
                for j, attrs in _unusual(values, kind, members, th).items():
                    for attr, sentence in attrs.items():
                        notes.setdefault(j, {}).setdefault(attr, sentence)
            if len(notes) > LISTED:
                issues.append(f"page {pg.n} has {len(notes)} values that differ from their neighbours; the first {LISTED} are listed")
            for j in sorted(notes, key=lambda j: (values[j]["bbox"][1], values[j]["bbox"][0]))[:LISTED]:
                s, attrs = values[j], notes[j]
                out.append(Finding(
                    fclass="observation", detector=DETECTOR, family="visual",
                    title=f"Value set in a different {' and '.join(a for a in _ATTR if a in attrs)} from the values beside it (page {pg.n})",
                    detail=f'The value "{s["text"]}" on page {pg.n} is set in {s["font"]} at {s["size"]:g} pt in colour {s["colour"]}: '
                           + "; ".join(attrs[a] for a in _ATTR if a in attrs) + f". A size counts as different from {th.font_size_delta_pt:g} pt up; "
                           f"a group needs {_MIN_COLUMN} values in a column or {_MIN_LINE} on a line, and {_SHARE:.0%} of them must agree.",
                    evidence=[_evidence(doc, pg, s["bbox"], "the value set in a different font, size or colour", s["text"])]))
    if issues:
        out.append(limitation(DETECTOR, "Fonts of values only partly compared",
                              "Some pages were not fully compared for the font, size and colour of their values: " + "; ".join(issues[:10]) + ".",
                              [doc_evidence(doc.id, "page content")]))
    return out
