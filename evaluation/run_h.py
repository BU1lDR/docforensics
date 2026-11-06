"""Score the reused-mark detector (scope D, package H) on the pack of datagen/reuse_pack.py:

    python -m evaluation.run_h ext-dev [--cases N] [--start S] [--out DIR]
    python -m evaluation.run_h ext-test --once-at-freeze [--cases N] [--out DIR]

Each case is written to a temporary folder and run through read, classify and forensics, the stages the detector needs. The result is set
against the manifest, which only this scorer reads. In a case that repeats a signature or a stamp, the reuse observation of that kind whose two
marks lie on the manifest's boxes (IoU of at least score.PLACE) is a find; any other reuse observation is a stray one. In a genuine case every
reuse observation is a false one. The ink gap of every compared pair is kept, by kind and medium, so that the limit can be read against the
pairs, and the same counts are given at other limits. ext-dev is what the limit was fitted on, so its figures are in-sample; ext-test is read
once, on the frozen code."""
import argparse
import json
import platform
import shutil
import statistics
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from datagen import reuse_pack
from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.forensics import run_forensics
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.read import read_stage
from docforensics.understand.classify import classify_stage

from .run_eval import _git, peak_rss_mb
from .score import MEDIA, PLACE, iou

STAGES = {"read": read_stage, "classify": classify_stage, "forensics": run_forensics}
KINDS = ("signature", "stamp")
LIMITS = (0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0)  # the limits the counts are repeated at, to show what the choice costs


def run_one(p: dict, th: Thresholds, tmp: Path) -> dict:
    files, entry = reuse_pack.build_pack_case(p)
    t0 = time.perf_counter()
    _, cd, _ = create_case(tmp / p["case"], sorted(files.items()), th)
    case = run_case(cd, th, stages=STAGES)
    seconds = time.perf_counter() - t0
    names = {c.id: c.filename for c in case.documents}
    truth = {r["kind"]: {n: b[1:] for n, b in r["boxes"].items()} for r in entry["reuse"]}
    pairs = [{k: e.data[k] for k in ("kind", "ink", "hash_bits", "repeat")} for e in AuditLog(cd.audit_path).events() if e.event == "reuse_compared"]
    found, stray = False, 0
    for f in (f for f in case.findings if f.detector == "reuse"):
        kind = f.evidence[0].note.split()[0]
        at = (len(f.evidence) == 2 and kind in truth and {names[e.doc] for e in f.evidence} == set(truth[kind])
              and all(iou(e.box, truth[kind][names[e.doc]]) >= PLACE for e in f.evidence))
        if at and not found:
            found = True
        else:
            stray += 1
    return {"case": p["case"], "kind": p["kind"], "medium": p["medium"], "layout": p["layout"], "seconds": round(seconds, 2), "pairs": pairs,
            "found": found, "stray": stray, "compared": p["kind"] == "genuine" or any(d["kind"] == p["kind"] for d in pairs)}


def gaps(rows: list[dict], kind: str, copies: bool, media=None) -> list[float]:
    """The ink gap of the compared pairs of a kind: the repeated pairs (`copies`) or the separate ones, optionally of some media."""
    return [d["ink"] for r in rows if media is None or r["medium"] in media for d in r["pairs"]
            if d["kind"] == kind and (r["kind"] == kind) == copies]


def stats(xs: list[float]) -> str:
    return f"{len(xs)} | {min(xs):.1f} | {statistics.median(xs):.1f} | {max(xs):.1f}" if xs else "0 | - | - | -"


def format_report(rows: list[dict], run: dict) -> str:
    th = Thresholds()
    L = [f"# Reused marks (scope D, package H): {run['split']}, {run['when']}", "",
         f"Tool: commit {run['commit']}{' (tree not clean)' if run['dirty'] else ''}. Limit: repeat_ink = {th.repeat_ink:g} % (ink gap; the 64-bit "
         f"hash is logged and does not decide). {len(rows)} cases of datagen/reuse_pack.py, {run['seconds']:.0f} s in all, peak memory {run['peak_mb']:.0f} MB. "
         f"{run['machine']}.", "",
         "A find is the observation of the right kind with both marks on the manifest's boxes (IoU of at least "
         f"{PLACE:g}). A stray observation is any other reuse observation; in a genuine case every one is a false observation. "
         + ("ext-dev is what the limit was fitted on, so these figures are in-sample." if run["split"] == "ext-dev"
            else "This split was read once, on the frozen code."), "", "## Repeated marks found, by kind and medium", "",
         "| Kind | Medium | Cases | Found at their place | Not compared | Stray observations |", "|---|---|---|---|---|---|"]
    for kind in KINDS:
        for medium in MEDIA:
            sub = [r for r in rows if r["kind"] == kind and r["medium"] == medium]
            if sub:
                L.append(f"| {kind} | {medium} | {len(sub)} | {sum(r['found'] for r in sub)} | {sum(not r['compared'] for r in sub)} | {sum(r['stray'] for r in sub)} |")
        sub = [r for r in rows if r["kind"] == kind]
        L.append(f"| **{kind}** | all | {len(sub)} | {sum(r['found'] for r in sub)} | {sum(not r['compared'] for r in sub)} | {sum(r['stray'] for r in sub)} |")
    L += ["", "## Genuine cases (every document signed and pressed afresh)", "", "| Medium | Cases | Cases with a reuse observation | Observations |", "|---|---|---|---|"]
    for medium in (*MEDIA, None):
        sub = [r for r in rows if r["kind"] == "genuine" and (medium is None or r["medium"] == medium)]
        if sub:
            L.append(f"| {medium or '**all**'} | {len(sub)} | {sum(r['stray'] > 0 for r in sub)} | {sum(r['stray'] for r in sub)} |")
    L += ["", "## The ink gap of the compared pairs (%)", "", "Repeated pairs are the pair of the case's own kind in a case that repeats a mark; separate pairs are "
          "every other pair, which two signings or two pressings made.", "", "| Pair | Medium | Pairs | Smallest | Median | Largest |", "|---|---|---|---|---|---|"]
    for kind in KINDS:
        for copies in (True, False):
            for label, media in (("digital", ("digital",)), ("scanned", ("mild", "150dpi", "120dpi")), ("all", None)):
                L.append(f"| {kind}, {'repeated' if copies else 'separate'} | {label} | {stats(gaps(rows, kind, copies, media))} |")
    L += ["", "## The same counts at other limits", "", "Repeated pairs at or under the limit would be found; separate pairs at or under it would be false observations.", "",
          "| Limit (%) | Signatures found | Stamps found | Separate signature pairs flagged | Separate stamp pairs flagged |", "|---|---|---|---|---|"]
    for lim in LIMITS:
        c = {k: gaps(rows, k, True) for k in KINDS}
        s = {k: gaps(rows, k, False) for k in KINDS}
        L.append(f"| {lim:g} | {sum(x <= lim for x in c['signature'])} of {len(c['signature'])} | {sum(x <= lim for x in c['stamp'])} of {len(c['stamp'])} | "
                 f"{sum(x <= lim for x in s['signature'])} of {len(s['signature'])} | {sum(x <= lim for x in s['stamp'])} of {len(s['stamp'])} |")
    L += ["", "## Cases", "", "| Case | Kind | Medium | Layout | Found | Stray | Pairs (kind: ink gap, hash bits) |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['case']} | {r['kind']} | {r['medium']} | {r['layout']} | {'yes' if r['found'] else '-'} | {r['stray']} | "
                 + "; ".join(f"{d['kind']}: {d['ink']:.1f}, {d['hash_bits']}" for d in r["pairs"]) + " |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m evaluation.run_h", description="Score the reused-mark detector on the pack.")
    ap.add_argument("split", choices=sorted(reuse_pack.BASE))
    ap.add_argument("--cases", type=int, default=24)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--out", default="eval")
    ap.add_argument("--once-at-freeze", action="store_true", help="required for ext-test, which is read once, on the frozen code")
    a = ap.parse_args()
    if a.split == "ext-test" and not a.once_at_freeze:
        sys.exit("ext-test is read once, on the frozen code: pass --once-at-freeze")
    th, tmp, t0 = Thresholds(), Path(tempfile.mkdtemp(prefix="reuse-")), time.perf_counter()
    try:
        rows = []
        for p in reuse_pack.plan_pack(a.split, a.cases, a.start):
            rows.append(run_one(p, th, tmp))
            print(f"{p['case']} {p['kind']:9} {p['medium']:7} found={rows[-1]['found']} stray={rows[-1]['stray']} {rows[-1]['seconds']:.1f}s", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    run = {"split": a.split, "when": datetime.now().strftime("%d %b %Y %H:%M"), "commit": _git("rev-parse", "--short", "HEAD"), "dirty": bool(_git("status", "--porcelain")),
           "seconds": time.perf_counter() - t0, "peak_mb": peak_rss_mb(), "machine": f"{platform.system()} {platform.release()}, Python {platform.python_version()}"}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"reuse-{a.split}.json").write_text(json.dumps({"run": run, "rows": rows}, indent=1), encoding="utf-8", newline="\n")
    (out / f"reuse-{a.split}.md").write_text(format_report(rows, run), encoding="utf-8", newline="\n")
    print(out / f"reuse-{a.split}.md")


if __name__ == "__main__":
    main()
