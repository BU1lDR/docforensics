"""Score the compression-history check (scope D, package E) on the scans of datagen/ela_pack.py:

    python -m evaluation.run_e ext-dev [--cases N] [--start S] [--pipeline] [--out DIR]
    python -m evaluation.run_e dev [--cases N] [--out DIR]

The pack is written to a temporary folder, each scan is examined and the result is set against the manifest, whose `expect` was fixed
before the check existed. By default the check looks at the picture's pixels (`ela_regions`; this is what tuning uses). With
--pipeline the whole tool runs on the uploaded picture, which is what a dossier shows; the final figures come from that mode. The report
lists every case, so misses and false regions are in it, and keeps the cases the check cannot see by construction ("blind") apart.
`dev` is a guard, not a measure: the check over the picture files of the dev split, where it should be silent on a scan saved once.
ext-test is read once, at the freeze, with --once-at-freeze."""
import argparse
import io
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import psutil
from PIL import Image

from datagen import build as dev_build
from datagen import ela_pack
from datagen import scan as scan_module
from docforensics.config import Thresholds
from docforensics.forensics import ela as ela_module
from docforensics.ingest import create_case
from docforensics.pipeline import run_case

from .score import iou

ROOT = Path(__file__).resolve().parents[1]
LOCATED = 0.3  # IoU of a region with the edited box at which the edit counts as found at its place
# Robustness variants of the pack's hosts (the quality of the first save of each level; the pack has 85, 50, 35). They are reports, not tuning sets.
HOSTS = {"off-grid": {"mild": 82, "150dpi": 47, "120dpi": 33},        # libjpeg's tables at qualities between the steps of 5 the check tries
         "other-tables": {"mild": 71, "150dpi": 59, "120dpi": 59}}   # Photoshop-family tables (Pillow's presets); the numbers are the nearest libjpeg qualities
NOTES = {"off-grid": "The hosts were saved at qualities 82, 47 and 33 (the pack's 85, 50 and 35), between the steps of 5 the check tries.",
         "other-tables": "The hosts were written with Photoshop-family quantisation tables (Pillow's presets web_medium and web_low); the nearest libjpeg "
                         "qualities, 71 and 59, stand in for the host quality in the pack's `expect` rule. The last saves are libjpeg's."}
PRESET = {71: "web_medium", 59: "web_low"}
KNOBS = ("QUALITIES", "GAP", "MIN_DIP", "INK", "BLOCK", "MIN_INK", "Z", "MAX_DIP", "MIN_CELLS", "MIN_RATIO", "LISTED")
# A page whose last save is under this has no quality at least GAP below it to look for an earlier save at: the check cannot examine it, and
# "no region" on such a scan says nothing, so the reports count those scans next to every count of false flags.
LOW = ela_module.QUALITIES[1] + ela_module.GAP
CANNOT = f"last save under quality {LOW}, or none found"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def cannot_examine(row: dict) -> bool:
    return row["final"] is None or row["final"] < LOW


def touches(a, b) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def regions_of(jpeg: bytes, name: str, work: Path, th: Thresholds, pipeline: bool) -> dict:
    """What the check says of one picture: its regions' boxes, and in function mode the two saves it found."""
    if pipeline:
        _, cd, _ = create_case(work / "data", [(name, jpeg)], th)
        mine = [f for f in run_case(cd, th).findings if f.detector == ela_module.DETECTOR]
        return {"boxes": [list(ev.box) for f in mine if f.fclass == "observation" for ev in f.evidence], "final": None, "earlier": None,
                "limited": any(f.fclass == "processing_limitation" for f in mine)}
    r = ela_module.ela_regions(np.asarray(Image.open(io.BytesIO(jpeg)).convert("L")))
    return {"boxes": [list(g.box) for g in r.regions], "final": r.final, "earlier": r.earlier, "limited": False}


def look(entry: dict, jpeg: bytes, work: Path, th: Thresholds, pipeline: bool) -> dict:
    t0 = time.perf_counter()
    got = regions_of(jpeg, entry["file"], work, th, pipeline)
    truth, boxes = entry["box"], got["boxes"]
    return {"case": entry["case"], "kind": entry["kind"], "level": entry["level"], "expect": entry["expect"], "host": entry["host_quality"],
            "last_save": entry["final_quality"], "final": got["final"], "earlier": got["earlier"], "regions": len(boxes), "limited": got["limited"],
            "located": bool(truth) and any(iou(b, truth) > LOCATED for b in boxes),
            "stray": sum(not (truth and touches(b, truth)) for b in boxes), "seconds": round(time.perf_counter() - t0, 2)}


def tally(rows: list[dict]) -> dict:
    return {"n": len(rows), "region": sum(r["regions"] > 0 for r in rows), "located": sum(r["located"] for r in rows),
            "touch": sum(r["regions"] > r["stray"] for r in rows), "stray": sum(r["stray"] > 0 for r in rows), "limited": sum(r["limited"] for r in rows),
            "last_ok": sum(r["final"] == r["last_save"] for r in rows), "earlier_ok": sum(r["earlier"] == r["host"] for r in rows)}


def format_report(split: str, mode: str, rows: list[dict], run: dict) -> str:
    controls = [r for r in rows if r["expect"] == "none"]
    seen = [r for r in rows if r["expect"] == "seen"]
    blind = [r for r in rows if r["expect"] == "blind"]
    c, s, b = tally(controls), tally(seen), tally(blind)
    names = lambda sel: ", ".join(r["case"] for r in sel) or "none"  # noqa: E731
    out = [f"# Compression-history check on the {split} pack ({mode})" + (f" with hosts of the variant {run['hosts']}" if run.get("hosts") else ""), "",
           f"Run: {run['date']}, commit {run['commit']}{', working tree not clean' if run['dirty'] else ''}, {run['machine']}.",
           f"{len(rows)} cases (seeds {run['seeds'][0]} to {run['seeds'][1]}), {sum(r['seconds'] for r in rows):.0f} s in all, "
           f"{sum(r['seconds'] for r in rows) / max(len(rows), 1):.1f} s a case.",
           f"Constants of forensics/ela.py: {', '.join(f'{k}={v}' for k, v in run['knobs'].items())}.",
           *([NOTES[run["hosts"]] + " A robustness report: nothing was tuned on it."] if run.get("hosts") else []), "",
           "A case is `none` when the scan has no edit (saved once, or saved again unchanged), `seen` when its edit was made after an earlier "
           "save at least 10 quality points below the last, so that the earlier save left a mark the edited place does not share, and `blind` "
           "when the check cannot see it by construction (an edit with the page's own grid and quality, or a last save too close to the "
           "earlier one). That is fixed in datagen/ela_pack.py. Located: a region whose IoU with the edited box is above "
           f"{LOCATED}. Stray: a region that does not touch the edited box.", "", "## In short", "",
           f"- Scans without an edit ({c['n']}): a region on {c['region']}, which is a false flag"
           + (f" ({names([r for r in controls if r['regions']])})." if c["region"] else ".")
           + (f" {sum(map(cannot_examine, controls))} of them cannot be examined ({CANNOT})." if mode == "pixels" else ""),  # the other mode does not record the saves
           f"- Edits the check is meant to see ({s['n']}): a region at the edit on {s['located']}; a region anywhere on {s['region']}; "
           f"a stray region on {s['stray']}" + (f" ({names([r for r in seen if r['stray']])})." if s["stray"] else "."),
           f"- Edits it cannot see ({b['n']}, listed apart, not claimed): a region anyway on {b['region']}, touching the edit on {b['touch']}, at the edit (IoU above {LOCATED}) on {b['located']}"
           + (f"; a stray region on {b['stray']}." if b["stray"] else "."),
           f"- Missed among those it is meant to see: {names([r for r in seen if not r['located']])}.",
           f"- Pictures it declared not examined: {sum(r['limited'] for r in rows)}."]
    if mode == "pixels":
        out.append(f"- Saves found (cases meant to be seen): last save right on {s['last_ok']} of {s['n']}, earlier save right on {s['earlier_ok']} of {s['n']}.")
    out += ["", "## By kind and level", "", "| kind | level | expect | cases | region | touching | located | stray |", "|---|---|---|---|---|---|---|---|"]
    for kind in ela_pack.KINDS:
        for level in ela_pack.LEVELS:
            sel = [r for r in rows if r["kind"] == kind and r["level"] == level]
            if sel:
                t = tally(sel)
                out.append(f"| {kind} | {level} | {sel[0]['expect']} | {t['n']} | {t['region']} | {t['touch']} | {t['located']} | {t['stray']} |")
    out += ["", "## Every case", "", "| case | kind | level | expect | last save (pack) | earlier save (pack) | regions | located | stray | s |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        last, first = r["last_save"], r["host"]
        if mode == "pixels":
            last, first = f"{last} (found {r['final']})", f"{first} (found {r['earlier'] if r['earlier'] is not None else '-'})"
        out.append(f"| {r['case']} | {r['kind']} | {r['level']} | {r['expect']} | {last} | {first} | "
                   f"{r['regions']} | {'yes' if r['located'] else 'no'} | {r['stray']} | {r['seconds']} |")
    return "\n".join(out) + "\n"


def run_pack(split: str, n: int, start: int, pipeline: bool, out_dir: Path, hosts: str = "") -> list[dict]:
    th, work = Thresholds(), Path(tempfile.mkdtemp(prefix="docforensics-ela-"))
    try:
        manifest = json.loads(ela_pack.build_split(split, work / "pack", n, start).read_text(encoding="utf-8"))
        rows = []
        for entry in manifest["cases"]:
            rows.append(look(entry, (work / "pack" / entry["case"] / entry["file"]).read_bytes(), work / entry["case"], th, pipeline))
            r = rows[-1]
            print(f"{r['case']} {r['kind']:<12} {r['level']:<6} {r['expect']:<5} saves {r['final']}/{r['earlier']} regions {r['regions']} "
                  f"located {r['located']} stray {r['stray']} {r['seconds']} s", flush=True)
        seeds = [e["seed"] for e in manifest["cases"]]
        mode = "whole tool" if pipeline else "pixels"
        run = {"date": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"), "commit": _git("rev-parse", "--short", "HEAD") or "unknown",
               "dirty": bool(_git("status", "--porcelain")), "hosts": hosts, "seeds": (min(seeds, default=0), max(seeds, default=0)),
               "knobs": {k: getattr(ela_module, k) if k != "QUALITIES" else f"{ela_module.QUALITIES[0]}..{ela_module.QUALITIES[-1]} step 5" for k in KNOBS},
               "machine": f"{platform.system()} {platform.release()}, Python {platform.python_version()}, {psutil.cpu_count(logical=False)} cores, CPU only"}
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{split}{'-' + hosts if hosts else ''}-{'tool' if pipeline else 'pixels'}"
        (out_dir / f"{stem}.md").write_text(format_report(split, mode, rows, run), encoding="utf-8", newline="\n")
        (out_dir / f"{stem}.json").write_text(json.dumps({"run": run, "rows": rows}, indent=1), encoding="utf-8", newline="\n")
        return rows
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_dev(n: int, out_dir: Path) -> None:
    """The check over the scans of the dev split, which nobody tuned it on: silent on a scan saved once; what it says of the S1 and S2 edits."""
    work = Path(tempfile.mkdtemp(prefix="docforensics-ela-dev-"))
    try:
        manifest = json.loads(dev_build.build_split("dev", work, n).read_text(encoding="utf-8"))
        rows = []
        for entry in manifest["cases"]:
            edits = {m["doc"]: (m["method"], m["box"]) for m in entry["manipulations"] if m["method"] in ("S1", "S2")}
            for d in entry["docs"]:
                if not d["file"].endswith(".jpg"):
                    continue
                method, truth = edits.get(d["file"], ("", None))
                got = regions_of((work / entry["case"] / d["file"]).read_bytes(), d["file"], work, Thresholds(), False)
                rows.append({"case": entry["case"], "file": d["file"], "key": "genuine" if entry["genuine"] else method or "other", "level": entry["medium"],
                             "final": got["final"], "earlier": got["earlier"], "regions": len(got["boxes"]), "box": truth, "boxes": got["boxes"],
                             "touch": any(touches(b, truth) for b in got["boxes"]) if truth else False,
                             "located": bool(truth) and any(iou(b, truth) > LOCATED for b in got["boxes"])})
                print(rows[-1]["case"], rows[-1]["file"], rows[-1]["key"], rows[-1]["level"], "regions", rows[-1]["regions"], "saves", rows[-1]["final"], rows[-1]["earlier"], flush=True)
        run = {"date": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"), "commit": _git("rev-parse", "--short", "HEAD") or "unknown", "dirty": bool(_git("status", "--porcelain")),
               "machine": f"{platform.system()} {platform.release()}, Python {platform.python_version()}, {psutil.cpu_count(logical=False)} cores, CPU only",
               "knobs": {k: getattr(ela_module, k) if k != "QUALITIES" else f"{ela_module.QUALITIES[0]}..{ela_module.QUALITIES[-1]} step 5" for k in KNOBS}}
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "dev-guard.md").write_text(format_dev(rows, n, run), encoding="utf-8", newline="\n")
        (out_dir / "dev-guard.json").write_text(json.dumps({"run": run, "rows": rows}, indent=1), encoding="utf-8", newline="\n")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def format_dev(rows: list[dict], n: int, run: dict) -> str:
    names = {"genuine": "Scans of genuine cases (nothing changed)", "other": "Scans in changed cases that were not themselves changed as a picture",
             "S1": "S1 (part of another scan pasted in)", "S2": "S2 (a field erased and retyped on the scan)"}
    out = ["# Compression-history check on the scans of the dev split (a guard, not a measure)", "",
           f"Run: {run['date']}, commit {run['commit']}{', working tree not clean' if run['dirty'] else ''}, {run['machine']}.",
           f"Cases 0 to {n - 1} of the dev split (the same cases as eval/dev.md), picture files only; the check looks at their pixels. The pack in eval/e/ is what the check "
           f"was tuned on; nothing here was used to set a constant. Constants of forensics/ela.py: {', '.join(f'{k}={v}' for k, v in run['knobs'].items())}.",
           "In this split every scan is a 200-DPI JPEG saved at its level's quality (85, 50, 35); S1 and S2 end with one more save at quality 85. On a `mild` scan "
           "that makes both saves 85, which the check cannot tell apart, so no region is expected there; at 150dpi and 120dpi the earlier save is 50 or 35.", "",
           "## In short", ""]
    for key, label in names.items():
        sel = [r for r in rows if r["key"] == key]
        if not sel:
            continue
        line = f"- {label}: {len(sel)} scans, a region on {sum(r['regions'] > 0 for r in sel)}"
        if key in ("S1", "S2"):
            line += f", touching the edit on {sum(r['touch'] for r in sel)}, at the edit (IoU above {LOCATED}) on {sum(r['located'] for r in sel)}"
        else:
            line += f"; {sum(map(cannot_examine, sel))} of the {len(sel)} cannot be examined ({CANNOT})"
        out.append(line + ".")
    out += ["", "## S1 and S2 scans", "", "| case | file | edit | level | last save found | earlier save found | regions | touching | located |", "|---|---|---|---|---|---|---|---|---|"]
    for r in (r for r in rows if r["key"] in ("S1", "S2")):
        out.append(f"| {r['case']} | {r['file']} | {r['key']} | {r['level']} | {r['final']} | {r['earlier'] if r['earlier'] is not None else '-'} | {r['regions']} | "
                   f"{'yes' if r['touch'] else 'no'} | {'yes' if r['located'] else 'no'} |")
    flagged = [r for r in rows if r["regions"] and r["key"] in ("genuine", "other")]
    out += ["", "## Regions on scans nobody changed as a picture", ""] + ([f"- {r['case']} {r['file']} ({r['key']}, {r['level']}): {r['boxes']}" for r in flagged] or ["None."])
    out += ["", "## Every scan", "", "| case | file | kind | level | last save found | earlier save found | regions |", "|---|---|---|---|---|---|---|"]
    out += [f"| {r['case']} | {r['file']} | {r['key']} | {r['level']} | {r['final']} | {r['earlier'] if r['earlier'] is not None else '-'} | {r['regions']} |" for r in rows]
    return "\n".join(out) + "\n"


def use_hosts(variant: str) -> None:
    """Make the pack write its hosts the way `variant` says (see HOSTS)."""
    for level, quality in HOSTS[variant].items():
        scan_module.LEVELS[level] = (*scan_module.LEVELS[level][:4], quality)  # the pack reads its hosts' qualities from here
    if variant == "other-tables":
        save, simulate, host = Image.Image.save, ela_pack.simulate_scan, []

        def patched_save(self, fp, format=None, **params):
            if host and format == "JPEG" and params.get("quality") in PRESET:  # only the host's own save, not the pack's later ones
                params["quality"] = PRESET[params["quality"]]
            return save(self, fp, format, **params)

        def patched_simulate(*args, **kw):
            host.append(1)
            try:
                return simulate(*args, **kw)
            finally:
                host.pop()

        Image.Image.save, ela_pack.simulate_scan = patched_save, patched_simulate


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m evaluation.run_e", description="Score the compression-history check on its pack.")
    p.add_argument("split", choices=["ext-dev", "ext-test", "dev"])
    p.add_argument("--cases", type=int, default=None, help="how many cases (pack: 36; dev: 80, as eval/dev.md)")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--pipeline", action="store_true", help="run the whole tool on each picture instead of the check on its pixels")
    p.add_argument("--out", default="eval/e", help="where the report goes (default: eval/e)")
    p.add_argument("--hosts", choices=sorted(HOSTS), default="", help="write the pack's hosts another way (a robustness report, not a tuning set)")
    p.add_argument("--once-at-freeze", action="store_true", help="allow ext-test, which is read once, at the freeze")
    a = p.parse_args(argv)
    if a.split == "ext-test" and not a.once_at_freeze:
        sys.exit("ext-test is read once, at the freeze (--once-at-freeze)")
    if a.hosts:
        use_hosts(a.hosts)
    if a.split == "dev":
        run_dev(a.cases or 80, ROOT / a.out)
    else:
        run_pack(a.split, a.cases or 36, a.start, a.pipeline, ROOT / a.out, a.hosts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
