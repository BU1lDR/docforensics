"""Evidence crops (design 7.8): the part of the page a finding cites, padded, with the cited box outlined.
Each crop is a file in the case folder; the evidence points at it by `crop_path`. A crop that cannot be made is logged, not fatal."""
import math
from pathlib import Path

from PIL import Image, ImageDraw

from .model import Box, Case
from .pipeline import Ctx

PAD = 12  # px of page kept around the cited box
MAX_CROPS = 6  # per finding: one that cites a long stretch gets its first six crops; every piece still has its page and box
OUTLINE = (255, 0, 0)
_KEEP = 4  # page images held in memory at once


def _crop(page: Image.Image, box: Box, out: Path) -> None:
    x0, y0, x1, y1 = math.floor(box[0]), math.floor(box[1]), math.ceil(box[2]), math.ceil(box[3])
    cx0, cy0, cx1, cy1 = max(0, x0 - PAD), max(0, y0 - PAD), min(page.width, x1 + PAD), min(page.height, y1 + PAD)
    if cx1 <= cx0 or cy1 <= cy0:
        raise ValueError(f"box lies outside the page ({page.width} x {page.height} px)")
    crop = page.crop((cx0, cy0, cx1, cy1))
    ImageDraw.Draw(crop).rectangle((x0 - cx0, y0 - cy0, max(x0, x1 - 1) - cx0, max(y0, y1 - 1) - cy0), outline=OUTLINE, width=3)
    crop.save(out)


def crop_evidence(case: Case, ctx: Ctx) -> None:
    docs = {d.id: d for d in case.documents}
    held: dict[tuple[str, int], Image.Image] = {}  # oldest first

    def page_image(doc_id: str, n: int) -> Image.Image:
        if (doc_id, n) not in held:
            pages = docs[doc_id].pages
            if not 1 <= n <= len(pages):
                raise ValueError(f"{doc_id} has no page {n}")
            if len(held) >= _KEEP:
                held.pop(next(iter(held))).close()
            with Image.open(ctx.cd.root / pages[n - 1].image_path) as im:
                held[doc_id, n] = im.convert("RGB")
        return held[doc_id, n]

    made = 0
    for f in case.findings:
        for i, e in enumerate(f.evidence, 1):
            e.crop_path = None  # a re-run starts over
            if e.page == 0 or i > MAX_CROPS:  # whole-document evidence has no place on a page
                continue
            try:
                out = ctx.cd.crops / f"{f.id}-{i}.png"
                _crop(page_image(e.doc, e.page), e.box, out)
            except Exception as ex:
                ctx.audit.append("system", "crop_failed", {"finding": f.id, "evidence": i, "reason": f"{type(ex).__name__}: {ex}"[:200]})
                continue
            e.crop_path = out.relative_to(ctx.cd.root).as_posix()
            made += 1
    for im in held.values():
        im.close()
    ctx.audit.append("system", "crops_made", {"crops": made})
