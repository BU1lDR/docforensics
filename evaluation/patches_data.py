"""Scanned pages for the learned patch detector (Task 29): built by the generator, read once by the product's own reader, kept on disk.
The slices below are fixed before any model sees them. A `design` slice is what features and settings are chosen on; a `confirm` slice
is read once, at the end, with everything fixed. Only development seeds are used: the dev split (1_000_000 up) and the ext-dev pack of
the compression-history work (3_100_000 up). Never the test split, ext-test, or the 5_000_000 to 6_999_999 seeds of the probe cases.

    python -m evaluation.patches_data build dev-design --root D:/tmp/patches --budget-min 20     # resumable; run under the window protocol
    python -m evaluation.patches_data status --root D:/tmp/patches

The builder reads the manifest entries (that is where the edited boxes are), so it lives under evaluation/: the product never does."""
import argparse
import json
import shutil
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from datagen import ela_pack
from datagen.build import build_case as build_dev_case
from datagen.build import plan_cases as plan_dev
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.model import Case, Document, Page
from docforensics.pipeline import Ctx
from docforensics.read import read_stage
from docforensics.store import CaseDir, load_case, save_case

# slice -> (source, plan indices): dev has two lists, the S1 cases and the scanned genuine cases; ext-dev is the E pack in plan order
SLICES: dict[str, tuple[str, dict[str, range] | range]] = {
    "dev-design": ("dev", {"S1": range(0, 1080), "genuine": range(0, 216)}),            # 72 S1 cases, 36 scanned genuine cases
    "dev-confirm": ("dev", {"S1": range(3000, 3540), "genuine": range(3000, 3144)}),    # 36 and 24
    "xdev-design": ("ext-dev", range(0, 180)),                                          # 30 of each of the six kinds
    "xdev-confirm": ("ext-dev", range(5004, 5112)),                                     # 18 of each
}
NO_EDIT = "no pixel edit recorded"


def wanted(name: str) -> list[dict]:
    """The planned cases of a slice, in plan order."""
    source, spec = SLICES[name]
    if source == "ext-dev":
        assert isinstance(spec, range)
        return ela_pack.plan_cases("ext-dev", len(spec), spec.start)
    assert isinstance(spec, dict)
    plan = plan_dev("dev", max(r.stop for r in spec.values()))
    index = lambda p: int(p["case"].rsplit("-", 1)[1])  # noqa: E731
    return [p for p in plan if (p["method"] == "S1" and index(p) in spec["S1"])
            or (p["genuine"] and p["medium"] != "digital" and index(p) in spec["genuine"])]


def _ocr_with_threads(threads: int) -> None:
    """The shared reader with its thread count capped (the machine is shared with other sessions). Same models, same results to
    float rounding. It reaches into the reader's two private names; this module is a tool of the evaluation, not of the product."""
    from rapidocr import RapidOCR

    from docforensics.read import ocr
    inst = ocr.Ocr.__new__(ocr.Ocr)
    inst._engine = RapidOCR(params={"Global.log_level": "error", "EngineConfig.onnxruntime.intra_op_num_threads": threads,
                                    "EngineConfig.onnxruntime.inter_op_num_threads": 1})
    ocr.Ocr._shared = inst


def _entry_meta(source: str, p: dict, files: dict[str, bytes], entry: dict) -> dict:
    """What the loader needs of the manifest entry: per file, the box of the pixel edit (scan frame) or None, and what kind it was."""
    if source == "ext-dev":
        return {"case": p["case"], "source": source, "kind": entry["kind"], "level": entry["level"], "layout": entry["layout"],
                "expect": entry["expect"], "files": {ela_pack.FILE: {"edit": entry["box"], "kind": entry["kind"]}}}
    edits = {m["doc"]: m["box"] for m in entry["manipulations"] if m["method"] == "S1"}
    return {"case": p["case"], "source": source, "kind": p["method"] or "genuine", "level": entry["medium"], "layout": entry["layout"],
            "files": {name: {"edit": edits.get(name), "kind": "S1" if name in edits else NO_EDIT} for name in files}}


def build(name: str, root: Path, budget_s: float, threads: int = 3, th: Thresholds | None = None) -> tuple[int, int]:
    """Build and read the cases of a slice that are not on disk yet, until the budget is spent. Returns (done now, still to do)."""
    th = th or Thresholds()
    source = SLICES[name][0]
    todo = [p for p in wanted(name) if not (root / name / p["case"] / "meta.json").exists()]
    if not todo:
        return 0, 0
    _ocr_with_threads(threads)
    t0, done = time.monotonic(), 0
    for p in todo:
        if time.monotonic() - t0 > budget_s:
            break
        folder = root / name / p["case"]
        shutil.rmtree(folder, ignore_errors=True)  # the leftovers of a stopped run: meta.json is written last, so no meta.json means not done
        if source == "ext-dev":
            scan, entry = ela_pack.build_case(p)
            files = {ela_pack.FILE: scan}
        else:
            files, entry = build_dev_case(p)
        case, cd, audit = create_case(folder, list(files.items()), th)
        read_stage(case, Ctx(cd, audit, th))
        save_case(case, cd)
        (folder / "meta.json").write_text(json.dumps(_entry_meta(source, p, files, entry), indent=1), encoding="utf-8", newline="\n")
        done += 1
    return done, len(todo) - done


@dataclass
class PageRec:
    slice: str
    case: str          # the planned case, e.g. dev-0006
    source: str        # dev | ext-dev
    kind: str          # of the case: dev: S1 or genuine; ext-dev: genuine, resaved, pasted-field, pasted-block, retyped, aligned
    level: str
    layout: str
    file: str
    edit: list[float] | None   # the box of the pixel edit on this page, in the page's pixels
    cd: CaseDir
    doc: Document
    page: Page

    @property
    def edited(self) -> bool:
        return self.edit is not None


def pages(name: str, root: Path) -> Iterator[PageRec]:
    """Every OCR-read page of a slice that is built, in plan order. A page of a document with a recorded edit has `edit` set."""
    for p in wanted(name):
        folder = root / name / p["case"]
        if not (folder / "meta.json").exists():
            continue
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        cd = CaseDir(next((folder / "cases").iterdir()))
        case: Case = load_case(cd)
        for doc in case.documents:
            info = meta["files"].get(doc.filename)
            for pg in doc.pages:
                if pg.read_mode != "ocr" or info is None:
                    continue
                yield PageRec(name, meta["case"], meta["source"], meta["kind"], meta["level"], meta["layout"], doc.filename,
                              info["edit"] if pg.n == 1 else None, cd, doc, pg)


def share_inside(word_box, edit) -> float:
    """The share of the word's box that lies inside the edit box."""
    w = max(min(word_box[2], edit[2]) - max(word_box[0], edit[0]), 0.0)
    h = max(min(word_box[3], edit[3]) - max(word_box[1], edit[1]), 0.0)
    area = (word_box[2] - word_box[0]) * (word_box[3] - word_box[1])
    return w * h / area if area > 0 else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m evaluation.patches_data")
    ap.add_argument("what", choices=("build", "status"))
    ap.add_argument("slice", nargs="?", choices=sorted(SLICES))
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--budget-min", type=float, default=20.0)
    ap.add_argument("--threads", type=int, default=3)
    a = ap.parse_args()
    names = [a.slice] if a.slice else sorted(SLICES)
    if a.what == "status":
        for n in names:
            total = len(wanted(n))
            have = sum((a.root / n / p["case"] / "meta.json").exists() for p in wanted(n))
            print(f"{n}: {have} of {total} cases built")
        return
    if not a.slice:
        sys.exit("name the slice to build")
    done, left = build(a.slice, a.root, a.budget_min * 60, a.threads)
    print(f"{a.slice}: built {done} now, {left} still to do")


if __name__ == "__main__":
    main()
