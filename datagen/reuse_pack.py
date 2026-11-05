"""A pack for the reused-mark detector (scope D, H): cases of the same three documents as the splits, where the payslip and the
application carry the very same signature, or the statement and the application carry the very same stamp pressing, and genuine
cases beside them as controls. In a genuine case every document is signed and pressed afresh, so two of its marks are close but never
identical (datagen.signatures, datagen.marks). The pack draws with the same drawers and changes nothing in them: for a reuse case,
the one stream a mark is drawn from is replaced, while the case is built, by a stream of the case's own for every document.

The pack has seeds of its own, above the dev and test splits, so no seed of a split is a seed of the pack. `ext-dev` is what the limits
of the detector are fitted on; `ext-test` is measured once, on the frozen code. The manifest is the ground truth and only the scorer reads it."""
import json
import random
from collections import Counter
from contextlib import contextmanager, nullcontext
from pathlib import Path

from . import marks, signatures
from .build import KEYS, MIXED, build_case

BASE = {"ext-dev": 3_200_000, "ext-test": 4_200_000}  # the first seed of a pack: above the splits, clear of the ranges the other packs use
SPAN = 10_000                                          # the seeds a pack may use: its base up to its base plus this
LAYOUTS = {"ext-dev": ("A",), "ext-test": ("A", "B")}  # the dev split has one layout, the test split two
KINDS = ("genuine", "signature", "stamp")
MEDIA = MIXED                                          # what each kind goes through, in turn: digital PDFs, mild scans, 150 and 120 dpi scans
CARRIERS = {"signature": ("payslip", "loan_application"), "stamp": ("bank_statement", "loan_application")}  # by document type


def plan_pack(split: str, n: int, start: int = 0) -> list[dict]:
    """Cases `start` to `start + n` of a pack: the three kinds in turn, and each kind through the layouts and the media in turn."""
    if split not in BASE:
        raise ValueError(f"unknown pack split {split!r}")
    if start < 0 or n < 0 or start + n > SPAN:
        raise ValueError(f"cases {start} to {start + n} do not fit the {SPAN} seeds of a pack")
    seen: Counter = Counter()
    plan = []
    for i in range(start + n):
        kind = KINDS[i % len(KINDS)]
        k = seen[kind]
        seen[kind] += 1
        plan.append({"case": f"{split}-h-{i:04d}", "seed": BASE[split] + i, "kind": kind, "k": k,
                     "layout": LAYOUTS[split][k % len(LAYOUTS[split])], "medium": MEDIA[k % len(MEDIA)]})
    return plan[start:]


@contextmanager
def _same(kind: str, seed: int):
    """While it lasts, every signature (or every stamp) is drawn from one stream of the case's own instead of from the stream of the
    document that draws it, so that two documents carry the same drawing. The drawers are put back as they were."""
    if kind == "signature":
        real = signatures.draw
        signatures.draw = lambda sheet, person, rng, x, caption_y: real(sheet, person, random.Random(f"reuse/{seed}/signature"), x, caption_y)
        restore = lambda: setattr(signatures, "draw", real)  # noqa: E731
    else:
        real = marks._draw
        marks._draw = lambda sheet, what, name, rng, x, y: real(sheet, what, name, random.Random(f"reuse/{seed}/stamp") if what == "stamp" else rng, x, y)
        restore = lambda: setattr(marks, "_draw", real)  # noqa: E731
    try:
        yield
    finally:
        restore()


def build_pack_case(p: dict) -> tuple[dict[str, bytes], dict]:
    """The files of one planned case of the pack, by name, and its manifest entry: the entry of a genuine case of the splits, and
    `reuse`, the marks the case repeats (kind, the two files, where each mark is in its file), empty for a genuine case."""
    plain = {"case": p["case"], "seed": p["seed"], "layout": p["layout"], "medium": p["medium"], "method": None, "genuine": True, "k": p["k"]}
    with nullcontext() if p["kind"] == "genuine" else _same(p["kind"], p["seed"]):
        files, entry = build_case(plain)
    entry["genuine"] = p["kind"] == "genuine"
    entry["kind"] = p["kind"]
    entry["reuse"] = []
    if p["kind"] != "genuine":
        names = {d["type"]: d["file"] for d in entry["docs"]}
        docs = [names[t] for t in CARRIERS[p["kind"]]]
        boxes = {d["file"]: d["boxes"][p["kind"]] for d in entry["docs"] if d["file"] in docs}
        entry["reuse"] = [{"kind": p["kind"], "docs": docs, "boxes": boxes}]
    return files, entry


def build_pack(split: str, out: Path | str, n: int, start: int = 0) -> Path:
    """Cases `start` to `start + n` of a pack written under `out`, one folder a case, and `out/manifest.json`. Returns the manifest's path."""
    out = Path(out)
    entries = []
    for p in plan_pack(split, n, start):
        files, entry = build_pack_case(p)
        folder = out / p["case"]
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (folder / name).write_bytes(data)
        entries.append(entry)
    path = out / "manifest.json"
    path.write_text(json.dumps({"split": split, "pack": "reuse", "cases": entries}, indent=1), encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="python -m datagen.reuse_pack", description="Write cases of the reused-mark pack and their manifest.")
    ap.add_argument("split", choices=sorted(BASE))
    ap.add_argument("out", help="the folder to write to")
    ap.add_argument("--cases", type=int, default=24, help="how many cases (default: 24)")
    ap.add_argument("--start", type=int, default=0, help="the first case (default: 0)")
    a = ap.parse_args()
    print(build_pack(a.split, a.out, a.cases, a.start))
