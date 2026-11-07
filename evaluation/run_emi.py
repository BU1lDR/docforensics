"""Score the declared-EMI check (cross_emi) on the cases of datagen/emi_pack.py:

    python -m evaluation.run_emi ext-dev [--cases N] [--start S] [--out DIR]

The pack is written to a temporary folder, each case (an application and a bank statement) goes through the tool (ingest, then every registered
stage), and the findings of the check are set against the manifest's `expect`, which datagen/emi_pack.py fixed before the check was run on the
pack. Missed: a planted gap that was not shown. False flag: a finding on a case with nothing to find. One kind, lender-only, is a gap the check
cannot read; the report counts it apart. ext-test is read once, at the freeze, with --once-at-freeze."""
import argparse
import json
import platform
import re
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import psutil

from datagen import emi_pack
from docforensics.checks.cross import EMI
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case

from .run_structure import _git

ROOT = Path(__file__).resolve().parents[1]
GAP = re.compile(r"instalment|existing EMI")  # a comparison the dossier says it could not make, where it names this one


def look(entry: dict, files: dict[str, bytes], work: Path, th: Thresholds) -> dict:
    """What the check shows of one case when the whole tool runs on its files."""
    t0 = time.perf_counter()
    _, cd, _ = create_case(work / "data", sorted(files.items()), th)
    found = run_case(cd, th).findings  # every registered stage, as the tool runs
    mine = [f for f in found if f.detector == EMI]
    flags = [f for f in mine if f.fclass == "inconsistency"]
    shown = sorted(f.title for f in flags)
    return {"case": entry["case"], "kind": entry["kind"], "layout": entry["layout"], "medium": entry["medium"], "declared": entry["declared"],
            "total": entry["total"], "expect": sorted(entry["expect"]), "shown": shown,
            "total_ok": all(f"INR {entry['total']}" in f.detail for f in flags) and entry["total"] is not None if flags else None,
            "limitations": sorted(f.title for f in mine if f.fclass == "processing_limitation"),
            "gap": any(GAP.search(f.detail) for f in found if f.detector == "cross_checks"),
            "other": sorted(f"{f.detector}: {f.title}" for f in found if f.detector != EMI and f.fclass != "processing_limitation"),
            "missed": [t for t in entry["expect"] if t not in shown], "stray": [t for t in shown if t not in entry["expect"]],
            "seconds": round(time.perf_counter() - t0, 1)}


def format_report(split: str, rows: list[dict], run: dict) -> str:
    nothing = [r for r in rows if r["kind"] not in emi_pack.PLANTED]
    reads = [r for r in rows if r["kind"] in emi_pack.PLANTED and r["kind"] not in emi_pack.BLIND]
    blind = [r for r in rows if r["kind"] in emi_pack.BLIND]
    names = lambda sel: ", ".join(r["case"] for r in sel) or "none"  # noqa: E731
    said = lambda r: bool(r["gap"] or r["limitations"])  # noqa: E731  the dossier owns up: a comparison it could not make, or a doubtful reading
    flagged = [r for r in nothing if r["shown"]]
    found = [r for r in reads if not r["missed"]]
    missed = [r for r in reads if r["missed"]]
    told, silent = [r for r in missed if said(r)], [r for r in missed if not said(r)]
    unseen = [r for r in blind if r["shown"]]
    told_blind = [r for r in blind if r["gap"]]
    gaps = [r for r in rows if r["gap"]]
    doubtful = [r for r in rows if r["limitations"]]
    others = defaultdict(list)
    for r in rows:
        for t in r["other"]:
            others[t].append(r["case"])
    secs = sum(r["seconds"] for r in rows)
    out = [f"# Declared-EMI check on the {split} pack (whole tool)", "",
           f"Run: {run['date']}, commit {run['commit']}{', working tree not clean' if run['dirty'] else ''}, {run['machine']}.",
           f"{len(rows)} cases (seeds {run['seeds'][0]} to {run['seeds'][1]}), {secs:.0f} s in all, {secs / max(len(rows), 1):.1f} s a case.", "",
           "A case is a loan application and a bank statement of one month, as digital PDFs or as mild scans. Some rows of the statement are set by "
           "datagen/emi_pack.py, which also fixed, before the check was run on the pack, what each kind must show. The instalments are narrated with the "
           "words the check reads (EMI, instalment, loan), so this is a measurement by construction: it shows what the check does with those wordings on "
           "statements and applications made by this project's generator. It says nothing about how often a real instalment is narrated like that, and "
           "nothing about other layouts or other producers. The kind lender-only is a gap the check cannot read; it is counted apart.", "",
           "## In short", "",
           f"- Cases with nothing to find ({len(nothing)}): a finding on {len(flagged)}, which is a false flag"
           + (f" ({names(flagged)})." if flagged else "."),
           f"- Cases with a gap the check reads ({len(reads)}): found on {len(found)}; missed: {names(missed)}."]
    if missed:
        out.append(f"- Of the {len(missed)} misses, the dossier says it could not compare (or shows a possible extraction error) on {len(told)}"
                   + (f" ({names(told)})" if told else "") + f" and says nothing on {len(silent)}" + (f" ({names(silent)})." if silent else "."))
    out += [f"- In the cases found, the finding named the instalments' total correctly on {sum(bool(r['total_ok']) for r in found)} of {len(found)}"
            + (f" (not on {names([r for r in found if not r['total_ok']])})." if any(not r["total_ok"] for r in found) else "."),
            f"- Cases with a gap the check cannot read ({len(blind)}, kind lender-only): found on {len(unseen)}"
            + (f" ({names(unseen)})." if unseen else ".")
            + (f" The dossier said it could not compare on {len(told_blind)} of them ({names(told_blind)})." if told_blind else ""),
            f"- Cases where the dossier says the check could not compare: {len(gaps)}" + (f" ({names(gaps)})." if gaps else "."),
            f"- Possible extraction errors raised by the check (a difference read from a doubtful figure or page, shown as a limitation): {len(doubtful)}"
            + (f" ({names(doubtful)})." if doubtful else "."),
            f"- Findings of other checks on these cases: {sum(map(len, others.values()))}"
            + (" (" + "; ".join(f"{t} on {', '.join(c)}" for t, c in sorted(others.items())) + ")." if others else "."),
            "", "## By kind", "", "| kind | gap | cases | found | missed | missed, said so | missed, silent | false flags |", "|---|---|---|---|---|---|---|---|"]
    for kind in emi_pack.KINDS:
        sel = [r for r in rows if r["kind"] == kind]
        if sel:
            planted = kind in emi_pack.PLANTED
            out.append(f"| {kind} | {('yes, not readable' if kind in emi_pack.BLIND else 'yes') if planted else 'no'} | {len(sel)} | "
                       f"{sum(bool(r['shown']) for r in sel)} | {sum(bool(r['missed']) for r in sel)} | "
                       f"{sum(bool(r['missed']) and said(r) for r in sel)} | {sum(bool(r['missed']) and not said(r) for r in sel)} | "
                       f"{sum(bool(r['stray']) for r in sel)} |")
    out += ["", "## By medium and layout", "", "| medium | layout | cases | gaps read: found of planted | missed, said so | missed, silent | false flags |",
            "|---|---|---|---|---|---|---|"]
    for medium in ("digital", "scan"):
        for layout in ("A", "B"):
            sel = [r for r in rows if r["medium"] == medium and r["layout"] == layout]
            if sel:
                planted = [r for r in sel if r["kind"] in emi_pack.PLANTED and r["kind"] not in emi_pack.BLIND]
                out.append(f"| {medium} | {layout} | {len(sel)} | {sum(not r['missed'] for r in planted)} of {len(planted)} | "
                           f"{sum(bool(r['missed']) and said(r) for r in planted)} | {sum(bool(r['missed']) and not said(r) for r in planted)} | "
                           f"{sum(bool(r['stray']) for r in sel if r['kind'] not in emi_pack.PLANTED)} |")
    out += ["", "## Every case", "", "| case | kind | layout | medium | declared | instalments | expected | shown | total named | limitations | not compared | other findings | s |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['case']} | {r['kind']} | {r['layout']} | {r['medium']} | {r['declared']} | {r['total'] or '-'} | {'yes' if r['expect'] else '-'} | "
                   f"{'yes' if r['shown'] else '-'} | {'-' if r['total_ok'] is None else 'yes' if r['total_ok'] else 'no'} | "
                   f"{'; '.join(r['limitations']) or '-'} | {'yes' if r['gap'] else '-'} | {'; '.join(r['other']) or '-'} | {r['seconds']} |")
    return "\n".join(out) + "\n"


def run_pack(split: str, n: int, start: int, out_dir: Path) -> list[dict]:
    th, work = Thresholds(), Path(tempfile.mkdtemp(prefix="docforensics-emi-"))
    try:
        manifest = json.loads(emi_pack.build_split(split, work / "pack", n, start).read_text(encoding="utf-8"))
        rows = []
        for entry in manifest["cases"]:
            files = {name: (work / "pack" / entry["case"] / name).read_bytes() for name in entry["files"]}
            rows.append(look(entry, files, work / entry["case"], th))
            r = rows[-1]
            print(f"{r['case']} {r['kind']:<16} {r['layout']} {r['medium']:<7} expected {len(r['expect'])} shown {len(r['shown'])} missed {len(r['missed'])} "
                  f"stray {len(r['stray'])} not-compared {int(r['gap'])} other {len(r['other'])} {r['seconds']} s", flush=True)
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
    p = argparse.ArgumentParser(prog="python -m evaluation.run_emi", description="Score the declared-EMI check on its pack.")
    p.add_argument("split", choices=["ext-dev", "ext-test"])
    p.add_argument("--cases", type=int, default=44, help="how many cases (default: 44, each kind in each layout and medium once)")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--out", default="eval/emi", help="where the report goes (default: eval/emi)")
    p.add_argument("--once-at-freeze", action="store_true", help="allow ext-test, which is read once, at the freeze")
    a = p.parse_args(argv)
    if a.split == "ext-test" and not a.once_at_freeze:
        sys.exit("ext-test is read once, at the freeze (--once-at-freeze)")
    run_pack(a.split, a.cases, a.start, ROOT / a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
