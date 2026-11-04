"""Image noise of a scan (design 7.5, S1 and S2). A scanner puts about the same grain over the whole page; paper filled in from its
surroundings has less of it, and a piece taken from another scan has the grain of that scan. Per word, the grain is the spread of
the part of the picture that a light blur takes away (the residual), measured on the paper beside the ink, and set against the
median over the words of the page. Only a difference is reported, and only as an observation: grain is changed by many innocent
things, by the scanner's white clip and a second JPEG save among them."""
import cv2
import numpy as np
from PIL import Image

from ..findings import doc_evidence, limitation, quote
from ..model import Case, Document, Evidence, Finding, Page
from ..pipeline import Ctx

DETECTOR = "scan_noise"
LISTED = 12      # words named in one finding; more are counted
MIN_WORDS = 8    # words that must be measurable before the page has a median worth comparing with
_BLUR = 1.5      # sigma in px of the blur whose difference is the residual
_MIN_PIXELS = 100  # paper pixels a word needs before its grain is measured (the word box as the reader gives it, no padding: a padded
#                    box around a small erased patch is mostly the untouched paper around it, which hides the patch)
_CLIPPED = 250   # paper brighter than this is cut at white by the scanner: its grain is not comparable and is left out


def _paper_grain(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The residual of the picture, and a mask of the pixels that are paper: away from ink, and not clipped at white."""
    u8 = gray.astype(np.uint8)
    background = cv2.medianBlur(u8, 31)
    ink = cv2.dilate((gray < background.astype(np.float32) - 40).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    residual = gray - cv2.GaussianBlur(gray, (0, 0), _BLUR)
    return residual, ~ink & (background <= _CLIPPED)


def _skipped(page: Page, why: str) -> str:
    return f"Page {page.n} ({page.quality_class}): {why}"


def noise_residual(case: Case, doc: Document, ctx: Ctx) -> list[Finding]:
    th = ctx.th
    out: list[Finding] = []
    issues: list[str] = []
    for pg in doc.pages:
        if pg.read_mode != "ocr":
            continue
        if pg.quality_class == "poor":
            issues.append(f"page {pg.n} is of poor quality (class poor), so the grain of its words was not compared")
            continue
        with Image.open(ctx.cd.root / pg.image_path) as im:
            gray = np.asarray(im.convert("L"), dtype=np.float32)
        residual, paper = _paper_grain(gray)
        h, w = gray.shape
        measured: list[tuple[float, object]] = []
        for word in pg.words:
            x0, y0, x1, y1 = word.box
            sl = (slice(max(int(y0), 0), min(int(y1) + 1, h)), slice(max(int(x0), 0), min(int(x1) + 1, w)))
            cells = residual[sl][paper[sl]]
            if cells.size >= _MIN_PIXELS:
                measured.append((float(cells.std()), word))
        if len(measured) < MIN_WORDS:
            issues.append(f"page {pg.n} has {len(measured)} words whose grain could be measured, fewer than the {MIN_WORDS} needed")
            continue
        median = float(np.median([s for s, _ in measured]))
        if median <= 0:
            issues.append(f"page {pg.n} has no measurable grain")
            continue
        odd = [(s / median, s, word) for s, word in measured if s / median < th.noise_ratio_lo or s / median > th.noise_ratio_hi]
        if not odd:
            continue
        odd.sort(key=lambda t: abs(np.log(t[0])), reverse=True)
        less = sum(1 for r, _, _ in odd if r < 1)
        kinds = " and ".join(f"{n} with {k} grain" for n, k in ((less, "less"), (len(odd) - less, "more")) if n)
        words = '"; "'.join(quote(w.text) for _, _, w in odd[:LISTED])
        more = f" and {len(odd) - LISTED} more" if len(odd) > LISTED else ""
        ev = [Evidence(doc=doc.id, page=pg.n, box=tuple(float(v) for v in w.box), value=quote(w.text),
                       note=f"grain {s:.2f} against a page median of {median:.2f} (ratio {r:.2f})") for r, s, w in odd[:LISTED]]
        weak = " The page is degraded, which makes the grain less comparable." if pg.quality_class == "degraded" else ""
        out.append(Finding(
            fclass="observation", detector=DETECTOR, family="visual", title=f"Image grain differs from the rest of the page (page {pg.n})",
            detail=f'On page {pg.n}, {len(odd)} of {len(measured)} measured words have a grain that differs from the page median ({median:.2f}) '
                   f'by a ratio below {th.noise_ratio_lo:g} or above {th.noise_ratio_hi:g}: {kinds}. Words: "{words}"{more}. Grain is the spread of '
                   f"the picture left after a blur of {_BLUR:g} px, measured on the paper beside the ink; paper brighter than {_CLIPPED} is left "
                   f"out because the scanner cuts it at white.{weak}", evidence=ev))
    if issues:
        out.append(limitation(DETECTOR, "Image grain only partly compared", "The grain of words was not compared everywhere: " + "; ".join(issues[:10]) + ".",
                              [doc_evidence(doc.id, "scanned pages")]))
    return out
