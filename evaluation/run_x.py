"""Run the pack of invoices and electricity bills with a local model and score what it read (package X, scope D):

    python -m evaluation.run_x ext-dev --model phi4-mini:3.8b --cases 8 --out eval/x [--budget MINUTES]
    python -m evaluation.run_x ext-dev --cases 8 --replay eval/x/ext-dev-phi4-mini-3-8b.json --out eval/x
    python -m evaluation.run_x ext-test --once-at-freeze --model phi4-mini:3.8b --cases N --out DIR

The model's replies are saved with the scores, so the scoring can be repeated without the model. A prompt the saved file does not hold
reads nothing. A case that cannot finish counts every fact of its documents as missing, with the error beside it. ext-test is read once, on
the frozen code, and says so with --once-at-freeze (a replay of it too). A live run in which the model answered nothing (Ollama not
running, the model not pulled, every call failing) exits 1 and writes no report: the scores of a model that was not there say nothing."""
import argparse
import copy
import json
import platform
import re
import shutil
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from datagen.unseen import build_split
from docforensics.config import Thresholds
from docforensics.explain.llm import DEFAULT_MODEL, LLMError, OllamaClient, _sha
from docforensics.ingest import create_case
from docforensics.pipeline import run_case

from .run_eval import _git
from .score_x import OUTCOMES, format_report, score_case, summarise


class NoModelReply(RuntimeError):
    """A live run in which the model answered nothing: its report would score a model that was not there as having read nothing."""


class Tape:
    """A client that keeps what it was asked and what it answered, or, given a saved file, answers from that file alone."""

    def __init__(self, inner=None, saved: dict | None = None) -> None:
        run = (saved or {}).get("run", {})
        self.inner, self.replies = inner, dict((saved or {}).get("replies", {}))
        self.model = inner.model if inner else run["model"]
        self.timeout = inner.timeout if inner else run.get("timeout", 180.0)
        self._digest = run.get("digest", "")

    def digest(self) -> str:
        return self.inner.digest() if self.inner else self._digest

    def chat_json(self, system: str, user: str, schema: dict) -> dict:
        key, sys_sha = _sha(user), _sha(system)
        if self.inner is None:
            got = self.replies.get(key)
            if got is None or got["system"] != sys_sha:
                raise LLMError("no saved reply for this prompt")
            if "error" in got:
                raise LLMError(got["error"])
            return copy.deepcopy(got["reply"])
        t0 = time.perf_counter()
        try:
            out = self.inner.chat_json(system, user, schema)
        except LLMError as e:
            self.replies[key] = {"system": sys_sha, "error": f"{type(e).__name__}: {e}", "seconds": round(time.perf_counter() - t0, 1)}
            raise
        self.replies[key] = {"system": sys_sha, "reply": out, "seconds": round(time.perf_counter() - t0, 1)}
        return out

    def seconds(self, events: list[dict]) -> list[float]:
        return [self.replies[e["prompt_sha256"]]["seconds"] for e in events if e.get("prompt_sha256") in self.replies]


def slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def run(split: str, n: int, start: int, out_dir, client=None, replay=None, model: str = DEFAULT_MODEL, budget_min: float | None = None) -> dict:
    """Cases `start` to `start + n` of the pack, read with `client` (default: Ollama, `model`) or from the saved file `replay`; the scores
    are returned, and the report (.md) and the replies with the per-fact rows (.json) are written to `out_dir`. A live run in which the model
    answered nothing raises NoModelReply and writes nothing."""
    out_dir = Path(out_dir)
    saved = json.loads(Path(replay).read_text(encoding="utf-8")) if replay else None
    tape = Tape(None if replay else (client or OllamaClient(model)), saved)
    if not replay and not tape.digest():
        raise NoModelReply(f"Ollama does not have {tape.model} (is it running, and is the model pulled?): nothing was run and no report was written")
    th, work, t_start = Thresholds(), Path(tempfile.mkdtemp(prefix="docforensics-x-")), time.monotonic()
    try:
        manifest = json.loads(build_split(split, work / "pack", n, start).read_text(encoding="utf-8"))
        results, errors = [], {}
        for entry in manifest["cases"]:
            if budget_min is not None and time.monotonic() - t_start > budget_min * 60:
                print(f"budget of {budget_min} minutes used: stopping before {entry['case']}", flush=True)
                break
            folder = work / "pack" / entry["case"]
            case, events = None, []
            try:
                _, cd, audit = create_case(work / "data", [(d["file"], (folder / d["file"]).read_bytes()) for d in entry["docs"]], th)
                case = run_case(cd, th, llm=tape)
                events = [e.data for e in audit.events() if e.event == "llm_extraction"]
            except Exception as e:  # one case that cannot finish must not hide the rest
                errors[entry["case"]] = f"{type(e).__name__}: {e}"
            results.append(score_case(entry, case, events, tape.seconds(events)))
            got = Counter(r["outcome"] for r in results[-1]["fields"])
            print(f"{entry['case']} ({entry['medium']}): " + ", ".join(f"{got[o]} {o}" for o in OUTCOMES), flush=True)
        if not replay and not any("reply" in r for r in tape.replies.values()):
            why = next((r["error"] for r in tape.replies.values() if "error" in r), "no call was made")
            raise NoModelReply(f"the model answered no call ({why}): no report was written")
        s = summarise(results)
        seeds = [e["seed"] for e in manifest["cases"][:len(results)]]
        s["run"] = {"model": tape.model, "digest": tape.digest(), "timeout": tape.timeout, "split": split, "start": start, "requested": n,
                    "seeds": (min(seeds, default=0), max(seeds, default=0)), "replayed": bool(replay), "errors": errors,
                    "date": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"), "commit": _git("rev-parse", "--short", "HEAD") or "unknown",
                    "dirty": bool(_git("status", "--porcelain")),
                    "machine": f"{platform.system()} {platform.release()}, Python {platform.python_version()}, CPU only"}
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = out_dir / f"{split}-{slug(tape.model)}"
        stem.with_suffix(".md").write_text(format_report(s), encoding="utf-8", newline="\n")
        stem.with_suffix(".json").write_text(json.dumps({"run": s["run"], "replies": tape.replies, "results": results}, indent=1), encoding="utf-8", newline="\n")
        return s
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m evaluation.run_x", description="Run the pack of invoices and electricity bills with a local model and score it.")
    p.add_argument("split", choices=["ext-dev", "ext-test"])
    p.add_argument("--cases", type=int, default=8, help="how many cases (default: 8)")
    p.add_argument("--start", type=int, default=0, help="the first case (default: 0)")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"the Ollama model (default: {DEFAULT_MODEL})")
    p.add_argument("--replay", metavar="FILE", help="score from the replies saved in FILE instead of running the model")
    p.add_argument("--budget", type=float, metavar="MINUTES", help="start no new case after this many minutes")
    p.add_argument("--out", default="eval/x", help="where the report and the saved replies go (default: eval/x)")
    p.add_argument("--once-at-freeze", action="store_true", help="required for ext-test, which is read once, on the frozen code")
    a = p.parse_args(argv)
    if a.split == "ext-test" and not a.once_at_freeze:
        p.error("ext-test is read once, on the frozen code: pass --once-at-freeze")
    try:
        s = run(a.split, a.cases, a.start, a.out, replay=a.replay, model=a.model, budget_min=a.budget)
    except NoModelReply as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"{a.split}: {s['cases']} cases, {s['facts']} facts: " + ", ".join(f"{s['outcomes'][k]} {k}" for k in OUTCOMES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
