"""Scanned payslips for measuring the compression-history detector (scope D, package E). One page a case, a JPEG scan at 200 dpi in one of
the three levels of datagen/scan.py (saved once, at the level's quality). The kinds, fixed here before any detector ran on them:

- genuine: the scan as the scanner saved it. Nothing to find.
- resaved: the genuine scan opened and saved again at quality 95, as a mailer or a converter would. Nothing to find.
- pasted-field: the region of the net pay pasted over from a scan of another payslip of the same level, taken 3 px right and 5 px down of
  where it lies (so its JPEG blocks do not fall on the host's), and the page saved at 95.
- pasted-block: the same for the block of gross earnings, total deductions and net pay.
- retyped: stock S2 (datagen/manipulate.py): the box of the net pay filled in from the paper around it and another amount typed in; saved at 85.
- aligned: stock S1: the same place of a scan of another payslip of the same level pasted in; saved at 85. Same level, same place, so the
  region has the host's own history: the test cannot tell it by construction.

`expect` says what the test can do on the case, by one rule written here: "none" for the first two; for the pasted kinds and `retyped`,
"seen" when the last save is at least 10 above the level's own quality (two steps of the grid the test looks at: the earlier save then
shows as a history of its own that the edited region does not share) and "blind" when it is not; "blind" for `aligned`. A "blind" case is
a miss the test is not claimed to cover, and the report lists it apart. Seeds: the split's base plus PACK, apart from every other pack."""
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .fictional import identity
from .manipulate import _gray, s1_splice, s2_erase_retype
from .scan import LEVELS as QUALITY
from .scan import simulate_scan, to_scan_frame
from .layouts import money
from .layouts.payslip import draw_payslip

BASE = {"ext-dev": 3_000_000, "ext-test": 4_000_000}  # the seed bases of the ext splits, as in the pack of package X
PACK = 100_000  # that pack draws its seeds from BASE + 0 on
SPAN = 10_000
LEVELS = ("mild", "150dpi", "120dpi")
KINDS = ("genuine", "resaved", "pasted-field", "pasted-block", "retyped", "aligned")
FINAL = {"resaved": 95, "pasted-field": 95, "pasted-block": 95, "retyped": 85, "aligned": 85}  # the quality of the last save
SHIFT = (3, 5)  # px of the donor's crop right and down of where it is pasted: no multiple of 8
FILE = "scan.jpg"


def plan_cases(split: str, n: int, start: int = 0) -> list[dict]:
    """Cases `start` to `start + n`: the kind cycles through the six, the level through the three every six cases, the layout every eighteen."""
    if split not in BASE:
        raise ValueError(f"unknown split {split!r}")
    if start < 0 or n < 0 or start + n > SPAN:
        raise ValueError(f"cases {start} to {start + n} do not fit the {SPAN} seeds of the pack")
    return [{"case": f"{split}-e-{i:04d}", "seed": BASE[split] + PACK + i, "kind": KINDS[i % 6], "level": LEVELS[(i // 6) % 3],
             "layout": "AB"[(i // 18) % 2]} for i in range(start, start + n)]


def _save(a: np.ndarray, quality: int) -> bytes:
    out = io.BytesIO()
    Image.fromarray(a).save(out, "JPEG", quality=quality)
    return out.getvalue()


def _box(truth: dict, names: list[str], size: tuple[int, int], scan_seed: int, margin: int) -> list[int]:
    """The box round the printed facts `names`, on the scan the seed makes, with a margin, kept inside the page."""
    boxes = [to_scan_frame(truth["boxes"][n][1:], size, scan_seed) for n in names]
    x0, y0, x1, y1 = min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)
    return [max(int(x0) - margin, 0), max(int(y0) - margin, 0), min(int(x1) + margin, size[0] - SHIFT[0]), min(int(y1) + margin, size[1] - SHIFT[1])]


def build_case(p: dict) -> tuple[bytes, dict]:
    """The scan of one planned case and its manifest entry."""
    seed, kind, level, scan_seed = p["seed"], p["kind"], p["level"], p["seed"] * 10
    host_q, final = QUALITY[level][4], FINAL.get(kind, QUALITY[level][4])
    ident = identity(seed)
    page = draw_payslip(ident, p["layout"], seed)
    scan = simulate_scan(page.pdf, level, scan_seed)
    size = Image.open(io.BytesIO(scan)).size
    box = shift = None
    note = {"genuine": "the scan as saved", "resaved": "the scan saved again at 95"}.get(kind, "")
    if kind == "resaved":
        scan = _save(_gray(scan), final)
    elif kind != "genuine":
        names = ["gross_earnings", "total_deductions", "net_pay"] if kind in ("pasted-block", "aligned") else ["net_pay"]
        box = _box(page.truth, names, size, scan_seed, 12 if kind == "pasted-block" else 8)
        if kind == "retyped":
            new = money(ident.net_pay + 1000 * (seed % 7 + 2))
            scan, _ = s2_erase_retype(scan, [float(v) for v in box], new)
            note = f"the net pay erased and {new!r} typed in"
        else:
            donor = simulate_scan(draw_payslip(identity(seed + 1), p["layout"], seed + 1).pdf, level, scan_seed + 1)
            if kind == "aligned":
                scan, _ = s1_splice(scan, donor, [float(v) for v in box])
                shift, note = [0, 0], "the same place of another payslip's scan pasted in"
            else:
                a, d = _gray(scan), _gray(donor)
                (x0, y0, x1, y1), (dx, dy) = box, SHIFT
                a[y0:y1, x0:x1] = d[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
                scan, shift, note = _save(a, final), list(SHIFT), "a region of another payslip's scan pasted in off the JPEG grid"
    expect = ("none" if box is None else "blind" if kind == "aligned" else "seen" if final >= host_q + 10 else "blind")
    return scan, {"case": p["case"], "seed": seed, "kind": kind, "level": level, "layout": p["layout"], "file": FILE, "host_quality": host_q,
                  "final_quality": final, "expect": expect, "box": box, "shift": shift, "note": note, "sha256": hashlib.sha256(scan).hexdigest()}


def build_split(split: str, out: Path | str, n: int, start: int = 0) -> Path:
    """Cases `start` to `start + n` written under `out`, one folder a case, and `out/manifest.json`. Returns the manifest's path."""
    out = Path(out)
    entries = []
    for p in plan_cases(split, n, start):
        scan, entry = build_case(p)
        (out / p["case"]).mkdir(parents=True, exist_ok=True)
        (out / p["case"] / FILE).write_bytes(scan)
        entries.append(entry)
    path = out / "manifest.json"
    path.write_text(json.dumps({"split": split, "pack": "e", "cases": entries}, indent=1), encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="python -m datagen.ela_pack", description="Write scans for the compression-history test and their manifest.")
    ap.add_argument("split", choices=sorted(BASE))
    ap.add_argument("out", help="the folder to write to")
    ap.add_argument("--cases", type=int, default=36, help="how many cases (default: 36)")
    ap.add_argument("--start", type=int, default=0, help="the first case (default: 0)")
    a = ap.parse_args()
    print(build_split(a.split, a.out, a.cases, a.start))
