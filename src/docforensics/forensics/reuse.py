"""Reused signatures (scope D, H). A hand signs afresh each time, so two signatures of one person come out close but never the same.
Two documents of one case that carry the very same image of a signature are worth a look. This is what signature.py cannot see: it
reports signatures that differ, and a signature copied from another document does not differ from it.

The canvases signature.py compares are measured again, tighter. The ink gap is their own distance with a reach of 1 px and a slide of
1 px and no turn: the share of the ink of the one that lies farther than 1 px from the ink of the other. A pair is the same image when
its ink gap is at most `repeat_ink` (config.py, set on the generated ext-dev pack, eval/h/reuse-ext-dev.md). The 64-bit difference hash
(dHash) of each canvas is worked out too and its distance is logged with the pair, but it does not decide: on ext-dev it did not
separate copies from separate signings, so a rule that required it only lost copies.

Stamps are not looked at, and neither are logos. A logo is the issuer's one design and is meant to repeat. Stamps were tried and left
out: two separate pressings of the generated stamp often matched as closely as a copy did, once the canvas was scaled and turned to its
best fit (eval/h/reuse-ext-dev-stamps.md), so no limit could keep the copies and drop the separate pressings. A pair of documents that
are the same file is skipped, since cross_duplicate reports it. So is a mark that fills more than half of its canvas (`_MAX_FILL`): a canvas is the
ink cut to its box and scaled to a fixed size, so a printed rule, a dot or a block fills it whatever its size, any two of them are the same
image, and none is a signature. The skip is logged (`reuse_skipped`). A plain mark that is not solid (a hollow box, a diagonal stroke) is compared, and one printed
the same on two documents will be reported. The result is an observation, never an inconsistency: a stored image of
a signature, placed by software, is an ordinary way for it to repeat. It says nothing about who signed. A signature that was drawn again
or traced is not found, and a scan adds noise that a tight limit cannot always see through."""
from itertools import combinations

import cv2
import numpy as np

from ..model import Case, Evidence, Finding
from ..pipeline import Ctx
from ..understand.specs import load_specs
from .signature import _SHIFT as _SIG_SHIFT
from .signature import _Sig, _locate as _locate_signature, distance, label

DETECTOR = "reuse"
_REACH = 1.0    # px on the canvas: ink farther than this from the other canvas's ink is unmatched
_SHIFT = 1      # px on the canvas: one canvas may slide this far over the other, either way and in each direction
_MAX_FILL = 0.5  # share of a canvas that is ink, above which the mark is a bar, a dot or a block and not a stroke (the generated hands fill a small part, eval/h/reuse-ext-dev.md)


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


def fill(c: np.ndarray, pad: int) -> float:
    """The share of a canvas (without its padding of `pad` px) that is ink."""
    return float(c[pad:-pad, pad:-pad].mean())


def bits(a: int, b: int) -> int:
    """The number of bits in which two hashes differ."""
    return (a ^ b).bit_count()


def _pair(a: _Sig, b: _Sig, ctx: Ctx) -> Finding | None:
    """Compare one pair of signatures, log it, and return the observation if the two are the same image."""
    if a.doc.sha256 == b.doc.sha256:
        return None
    th = ctx.th
    gap, apart = ink_gap(a.canvas, b.canvas), bits(dhash(a.canvas, _SIG_SHIFT), dhash(b.canvas, _SIG_SHIFT))
    same = bool(gap <= th.repeat_ink)
    ctx.audit.append("system", "reuse_compared", {"kind": "signature", "docs": [a.doc.id, b.doc.id], "pages": [a.page, b.page], "ink": round(gap, 2),
                                                  "limit_ink": th.repeat_ink, "hash_bits": apart, "repeat": same,
                                                  "fill": [round(fill(c, _SIG_SHIFT), 3) for c in (a.canvas, b.canvas)]})
    if not same:
        return None
    w, h = a.canvas.shape[1] - 2 * _SIG_SHIFT, a.canvas.shape[0] - 2 * _SIG_SHIFT
    return Finding(
        fclass="observation", detector=DETECTOR, family="visual",
        title=f"The signatures on {label(a.doc)} and on {label(b.doc)} are the same image",
        detail=f"The signature on page {a.page} of {label(a.doc)} and the one on page {b.page} of {label(b.doc)} match as closely as one image "
               f"matches itself. Each was straightened by the turn of its page, cut to its ink and scaled to {w} x {h} px. Then {gap:.1f} % of "
               f"the ink of the one lies more than {_REACH:g} px from the ink of the other, at the best placement of one over the other within "
               f"{_SHIFT} px and with no turn allowed (the limit is {th.repeat_ink:g} %). Two separate signings did not match this closely "
               f"in the synthetic documents the limit was set on. There are ordinary causes: software that places one stored image of the "
               f"signature on each document it makes, one page submitted in two forms, or a scan of one page used for two documents. This does "
               f"not say how the signature came to be on both documents, or whether either document is in doubt; the signatory can say.",
        evidence=[Evidence(doc=m.doc.id, page=m.page, box=m.box, note=f"signature on page {m.page}") for m in (a, b)])


def compare_reuse(case: Case, ctx: Ctx) -> list[Finding]:
    """Draft observations for the case: every pair of located signatures is compared and logged (`reuse_compared`), and a pair that is
    the same image is an observation. A signature that could not be located is a limitation of signature.py, which says so, and is
    skipped here. So is a mark that fills more than `_MAX_FILL` of its canvas, which is logged as `reuse_skipped`."""
    specs, sigs = load_specs(), []
    for doc in case.documents:
        spec = specs.get(doc.doc_type)
        got = _locate_signature(doc, spec.signature, ctx) if spec and spec.signature else None
        if isinstance(got, _Sig):
            share = fill(got.canvas, _SIG_SHIFT)
            if share > _MAX_FILL:
                ctx.audit.append("system", "reuse_skipped", {"doc": doc.id, "page": got.page, "fill": round(share, 3), "limit_fill": _MAX_FILL})
            else:
                sigs.append(got)
    return [f for a, b in combinations(sigs, 2) if (f := _pair(a, b, ctx))]
