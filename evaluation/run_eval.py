"""Build a split, run the pipeline over every case, score it against the manifest and write the report (Task 19):

    python -m evaluation.run_eval --split dev --out eval [--cases N] [--start S] [--keep DIR]

The split is built in a separate process, so the peak memory reported is the pipeline's alone. A case that cannot finish is a miss
in the report, with the error beside it; it does not stop the run."""
import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import psutil

from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case

from .score import format_report, score

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = {"dev": 80, "test": 144}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def peak_rss_mb() -> float:
    """The most memory this process has held. Windows keeps the peak; elsewhere psutil only has the current figure."""
    mem = psutil.Process().memory_info()
    return round(getattr(mem, "peak_wset", mem.rss) / 2**20, 1)


def evaluate(split: str, n: int, start: int, out_dir, keep=None, th: Thresholds | None = None) -> dict:
    """Cases `start` to `start + n` of a split, run and scored; the report goes to `<out_dir>/<split>.md`. `keep` is a folder to leave the
    generated files and the case folders in; without it they are written to a temporary folder and removed."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="docforensics-eval-"))
    th = th or Thresholds()
    try:
        subprocess.run([sys.executable, "-m", "datagen.build", split, str(work / "split"), "--cases", str(n), "--start", str(start)],
                       cwd=ROOT, check=True)
        manifest = json.loads((work / "split" / "manifest.json").read_text(encoding="utf-8"))
        results, timings, errors = {}, {}, {}
        for entry in manifest["cases"]:
            folder = work / "split" / entry["case"]
            files = [(d["file"], (folder / d["file"]).read_bytes()) for d in entry["docs"]]  # in the order the documents were drawn
            t0 = time.perf_counter()
            try:
                _, cd, _ = create_case(work / "data", files, th)
                results[entry["case"]] = run_case(cd, th)
            except Exception as e:  # one case that cannot finish must not hide the rest
                errors[entry["case"]] = f"{type(e).__name__}: {e}"
            timings[entry["case"]] = time.perf_counter() - t0
        res = score(manifest, results, timings, peak_rss_mb(), errors, th.low_conf)
        seeds = [e["seed"] for e in manifest["cases"]]
        res["run"] = {"split": split, "start": start, "cases": n, "seeds": (min(seeds, default=0), max(seeds, default=0)),
                      "date": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"), "commit": _git("rev-parse", "--short", "HEAD") or "unknown",
                      "dirty": bool(_git("status", "--porcelain")),
                      "machine": f"{platform.system()} {platform.release()}, Python {platform.python_version()}, {psutil.cpu_count(logical=False)} cores, CPU only"}
        (out_dir / f"{split}.md").write_text(format_report(res), encoding="utf-8", newline="\n")
        return res
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m evaluation.run_eval", description="Run the pipeline over a split of the demonstration dataset and write the report.")
    p.add_argument("--split", choices=sorted(DEFAULT_CASES), required=True)
    p.add_argument("--out", default="eval", help="where the report is written (default: eval)")
    p.add_argument("--cases", type=int, help="how many cases (default: 80 for dev, 144 for test)")
    p.add_argument("--start", type=int, default=0, help="the first case (default: 0)")
    p.add_argument("--keep", metavar="DIR", help="leave the generated files and the case folders in DIR")
    a = p.parse_args(argv)
    res = evaluate(a.split, a.cases or DEFAULT_CASES[a.split], a.start, a.out, a.keep)
    found = sum(r["found"] for r in res["methods"].values())
    total = sum(r["n"] for r in res["methods"].values())
    print(f"{a.split}: {found} of {total} changes found, {res['genuine']['flags']} flags on {res['genuine']['documents']} genuine documents, "
          f"{res['counts']['no_result']} cases without a result. Report: {Path(a.out) / (a.split + '.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
