"""Score the raw file-structure check (Task 27) on the files of datagen/structure_pack.py:

    python -m evaluation.run_structure ext-dev [--cases N] [--start S] [--out DIR]

The pack is written to a temporary folder, each file goes through the tool (ingest, read, forensics), and the observations of the
file-structure check are set against the manifest's `expect`, which datagen/structure_pack.py fixed before the check was run on the pack.
Missed: an expected observation that was not shown. Stray: an observation that was shown and is not expected (on a file without a planted
change, a false flag). The report lists every case. ext-test is read once, at the freeze, with --once-at-freeze."""
import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import psutil

from datagen import structure_pack
from docforensics.config import Thresholds
from docforensics.forensics import run_forensics
from docforensics.forensics.structure import DETECTOR
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.read import read_stage

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def look(entry: dict, data: bytes, work: Path, th: Thresholds) -> dict:
    """What the check shows of one file when the whole tool runs on it."""
    t0 = time.perf_counter()
    _, cd, _ = create_case(work / "data", [(entry["file"], data)], th)
    mine = [f for f in run_case(cd, th, stages={"read": read_stage, "forensics": run_forensics}).findings if f.detector == DETECTOR]
    shown = sorted(f.title for f in mine if f.fclass == "observation")
    return {"case": entry["case"], "kind": entry["kind"], "file": entry["file"], "bytes": len(data), "expect": sorted(entry["expect"]), "shown": shown,
            "limitations": sorted(f.title for f in mine if f.fclass == "processing_limitation"),
            "missed": [t for t in entry["expect"] if t not in shown], "stray": [t for t in shown if t not in entry["expect"]],
            "seconds": round(time.perf_counter() - t0, 1)}


def format_report(split: str, rows: list[dict], run: dict) -> str:
    plain = [r for r in rows if r["kind"] not in structure_pack.PLANTED]
    planted = [r for r in rows if r["kind"] in structure_pack.PLANTED]
    names = lambda sel: ", ".join(r["case"] for r in sel) or "none"  # noqa: E731
    shown_all = sum(len(r["expect"]) - len(r["missed"]) for r in planted)
    lims = Counter((r["kind"], t) for r in rows for t in r["limitations"])
    out = [f"# Raw file-structure check on the {split} pack (whole tool)", "",
           f"Run: {run['date']}, commit {run['commit']}{', working tree not clean' if run['dirty'] else ''}, {run['machine']}.",
           f"{len(rows)} cases (seeds {run['seeds'][0]} to {run['seeds'][1]}), {sum(r['seconds'] for r in rows):.0f} s in all, "
           f"{sum(r['seconds'] for r in rows) / max(len(rows), 1):.1f} s a case.", "",
           "A case without a planted change is a digital PDF, a PDF holding a scan, a JPEG or a PNG as the generator or the scanner wrote it. A planted case "
           "carries one change to the file's structure, and `expect` is the list of observations the check must show on it, fixed in datagen/structure_pack.py "
           "before the check was run on the pack. This is a measurement by construction: it shows what the check does with the changes it was written to look "
           "for, on files made by this project's generator. It says nothing about how often a real edit leaves such a change, and nothing about files made "
           "by other programs.", "", "## In short", "",
           f"- Files without a planted change ({len(plain)}): an observation on {sum(bool(r['shown']) for r in plain)}, which is a false flag"
           + (f" ({names([r for r in plain if r['shown']])})." if any(r["shown"] for r in plain) else "."),
           f"- Files with one planted change ({len(planted)}): every expected observation shown on {sum(not r['missed'] for r in planted)}; "
           f"{shown_all} of {sum(len(r['expect']) for r in planted)} expected observations shown. Missed: {names([r for r in planted if r['missed']])}.",
           f"- Observations that were not expected: {sum(len(r['stray']) for r in rows)}"
           + (f" (on {names([r for r in rows if r['stray']])})." if any(r["stray"] for r in rows) else "."),
           f"- Limitations the check raised: {sum(lims.values())}"
           + (": " + "; ".join(f"{kind}: {title} ({n})" for (kind, title), n in lims.items()) + "." if lims else "."),
           "", "## By kind", "", "| kind | planted | files | expected observations shown | missed | stray |", "|---|---|---|---|---|---|"]
    for kind in structure_pack.KINDS:
        sel = [r for r in rows if r["kind"] == kind]
        if sel:
            out.append(f"| {kind} | {'yes' if kind in structure_pack.PLANTED else 'no'} | {len(sel)} | "
                       f"{sum(len(r['expect']) - len(r['missed']) for r in sel)} of {sum(len(r['expect']) for r in sel)} | {sum(len(r['missed']) for r in sel)} | "
                       f"{sum(len(r['stray']) for r in sel)} |")
    out += ["", "## Every case", "", "| case | kind | file | bytes | expected | shown | limitations | s |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['case']} | {r['kind']} | {r['file']} | {r['bytes']} | {'; '.join(r['expect']) or '-'} | {'; '.join(r['shown']) or '-'} | "
                   f"{'; '.join(r['limitations']) or '-'} | {r['seconds']} |")
    return "\n".join(out) + "\n"


def run_pack(split: str, n: int, start: int, out_dir: Path) -> list[dict]:
    th, work = Thresholds(), Path(tempfile.mkdtemp(prefix="docforensics-structure-"))
    try:
        manifest = json.loads(structure_pack.build_split(split, work / "pack", n, start).read_text(encoding="utf-8"))
        rows = []
        for entry in manifest["cases"]:
            rows.append(look(entry, (work / "pack" / entry["case"] / entry["file"]).read_bytes(), work / entry["case"], th))
            r = rows[-1]
            print(f"{r['case']} {r['kind']:<18} expected {len(r['expect'])} shown {len(r['shown'])} missed {len(r['missed'])} stray {len(r['stray'])} "
                  f"limitations {len(r['limitations'])} {r['seconds']} s", flush=True)
        seeds = [e["seed"] for e in manifest["cases"]]
        run = {"date": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"), "commit": _git("rev-parse", "--short", "HEAD") or "unknown",
               "dirty": bool(_git("status", "--porcelain")), "seeds": (min(seeds, default=0), max(seeds, default=0)),
               "machine": f"{platform.system()} {platform.release()}, Python {platform.python_version()}, {psutil.cpu_count(logical=False)} cores, CPU only"}
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{split}.md").write_text(format_report(split, rows, run), encoding="utf-8", newline="\n")
        (out_dir / f"{split}.json").write_text(json.dumps({"run": run, "rows": rows}, indent=1), encoding="utf-8", newline="\n")
        return rows
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m evaluation.run_structure", description="Score the raw file-structure check on its pack.")
    p.add_argument("split", choices=["ext-dev", "ext-test"])
    p.add_argument("--cases", type=int, default=12, help="how many cases (default: 12, each kind once)")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--out", default="eval/structure", help="where the report goes (default: eval/structure)")
    p.add_argument("--once-at-freeze", action="store_true", help="allow ext-test, which is read once, at the freeze")
    a = p.parse_args(argv)
    if a.split == "ext-test" and not a.once_at_freeze:
        sys.exit("ext-test is read once, at the freeze (--once-at-freeze)")
    run_pack(a.split, a.cases, a.start, ROOT / a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
