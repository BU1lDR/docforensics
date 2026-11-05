"""Reused marks (scope D, H). A hand signs afresh each time and a stamp is pressed afresh each time, so two signatures of one person, or
two pressings of one stamp, come out close but never the same. Two documents of one case that carry the very same image of a signature,
or of a stamp, are worth a look. This is what signature.py and marks.py cannot see: they report marks that differ, and a mark copied
from another document does not differ from it.

The canvases those two compare are measured again, tighter, in two ways. The ink gap is their own distance with a reach of 1 px and a slide
of 1 px and no turn: the share of the ink of the one that lies farther than 1 px from the ink of the other. The hash distance is the number
of bits in which the 64-bit difference hashes (dHash) of the two canvases differ. A pair is the same image when its ink gap is at most
`repeat_ink` and its hash distance at most `repeat_hash` (config.py, fitted on the generated ext-dev pack, eval/reuse-dev.md). The hash
is coarse (a 9 x 8 grid of ink densities) and can say that two canvases are alike but not that they are identical; the tight ink gap is
what separates a copy from a second signing, and the report says what each measure alone does.

Only signatures and stamps are looked at, not logos: a logo is the issuer's one design and is meant to repeat. A pair of documents that
are the same file is skipped, since cross_duplicate reports it. The result is an observation, never an inconsistency: a stored image
of a signature or a stamp, placed by software, is an ordinary way for it to repeat. It says nothing about who signed or stamped.
A copy that was drawn again, traced or turned by more than a degree or two is not found, and a scan adds noise that a tight limit
cannot always see through."""
from itertools import combinations

import cv2
import numpy as np

from ..model import Case, Evidence, Finding
from ..pipeline import Ctx
from ..understand.specs import load_specs
from .marks import _SHIFT as _MARK_SHIFT
from .marks import _SIZE, _locate as _locate_mark, issuer_groups, _Mark
from .signature import _SHIFT as _SIG_SHIFT
from .signature import _Sig, _locate as _locate_signature, canvas, distance, label

DETECTOR = "reuse"
_REACH = 1.0    # px on the canvas: ink farther than this from the other canvas's ink is unmatched
_SHIFT = 1      # px on the canvas: one canvas may slide this far over the other, either way and in each direction
_ACT = {"signature": "signing", "stamp": "pressing"}


def ink_gap(a: np.ndarray, b: np.ndarray) -> float:
    """Percent of the ink of the one that lies farther than 1 px from the ink of the other (the larger of the two shares), at the best
    slide of one over the other within 1 px. The same measure as signature.distance, at a reach and a slide that only a second drawing
    of the same strokes keeps."""
    return distance(a, b, _REACH, _SHIFT)


def dhash(c: np.ndarray, pad: int) -> int:
    """The 64-bit difference hash of a canvas (a mask padded by `pad` px): its ink density on a grid of 9 x 8 cells, one bit for each
    pair of neighbours in a row, set where the left cell holds more ink than the right."""
    inner = c[pad:-pad, pad:-pad] if pad else c
    cells = cv2.resize(inner.astype(np.float32), (9, 8), interpolation=cv2.INTER_AREA)
    return sum(1 << i for i, bit in enumerate((cells[:, :-1] > cells[:, 1:]).ravel()) if bit)


def bits(a: int, b: int) -> int:
    """The number of bits in which two hashes differ."""
    return (a ^ b).bit_count()


def _pair(kind: str, a: _Sig | _Mark, b: _Sig | _Mark, ca: np.ndarray, cb: np.ndarray, pad: int, ctx: Ctx) -> Finding | None:
    """Compare one pair of marks of a kind, log it, and return the observation if the two are the same image."""
    if a.doc.sha256 == b.doc.sha256:
        return None
    th = ctx.th
    gap, apart = ink_gap(ca, cb), bits(dhash(ca, pad), dhash(cb, pad))
    same = bool(gap <= th.repeat_ink and apart <= th.repeat_hash)
    ctx.audit.append("system", "reuse_compared", {"kind": kind, "docs": [a.doc.id, b.doc.id], "pages": [a.page, b.page], "ink": round(gap, 2),
                                                  "hash": apart, "limit_ink": th.repeat_ink, "limit_hash": th.repeat_hash, "repeat": same})
    if not same:
        return None
    w, h = ca.shape[1] - 2 * pad, ca.shape[0] - 2 * pad
    return Finding(
        fclass="observation", detector=DETECTOR, family="visual",
        title=f"The {kind} on {label(a.doc)} and on {label(b.doc)} is the same image",
        detail=f"The {kind} on page {a.page} of {label(a.doc)} and the one on page {b.page} of {label(b.doc)} match as closely as one image "
               f"matches itself. Each was straightened by the turn of its page, cut to its ink and scaled to {w} x {h} px. Then {gap:.1f} % of "
               f"the ink of the one lies more than {_REACH:g} px from the ink of the other, at the best placement of one over the other within "
               f"{_SHIFT} px and with no turn allowed (the limit is {th.repeat_ink:g} %), and their 64-bit difference hashes differ in {apart} "
               f"bits (the limit is {th.repeat_hash}). Two separate {_ACT[kind]}s did not match this closely in the synthetic documents the "
               f"limits were fitted on. There are ordinary causes: software that places one stored image of the {kind} on each document it "
               f"makes, one page submitted in two forms, or a scan of one page used for two documents. This does not say how the {kind} came "
               f"to be on both documents, or whether either document is in doubt; the signatory or the issuer can say.",
        evidence=[Evidence(doc=m.doc.id, page=m.page, box=m.box, note=f"{kind} on page {m.page}") for m in (a, b)])


def compare_reuse(case: Case, ctx: Ctx) -> list[Finding]:
    """Draft observations for the case: every pair of located signatures, and every pair of located stamps of one issuer, is compared and
    logged (`reuse_compared`); a pair that is the same image is an observation. What could not be located is a limitation of
    signature.py or marks.py, which say so, and is skipped here."""
    specs, out = load_specs(), []
    sigs = []
    for doc in case.documents:
        spec = specs.get(doc.doc_type)
        got = _locate_signature(doc, spec.signature, ctx) if spec and spec.signature else None
        if isinstance(got, _Sig):
            sigs.append(got)
    for a, b in combinations(sigs, 2):
        if f := _pair("signature", a, b, a.canvas, b.canvas, _SIG_SHIFT, ctx):
            out.append(f)
    _, groups, _ = issuer_groups(case, ctx)
    for g in groups:
        stamps = []
        for doc, line in g:
            got = _locate_mark("stamp", doc, specs[doc.doc_type], line, ctx) if specs[doc.doc_type].stamp else None
            if isinstance(got, _Mark):
                stamps.append(got)
        for a, b in combinations(stamps, 2):
            if f := _pair("stamp", a, b, canvas(a.ink, a.turn, _SIZE, _MARK_SHIFT), canvas(b.ink, b.turn, _SIZE, _MARK_SHIFT), _MARK_SHIFT, ctx):
                out.append(f)
    return out
