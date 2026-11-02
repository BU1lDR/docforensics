"""Stage runner. Stages are plain functions over the case; each runs under guarded() and is logged (design 4, 7.10)."""
import platform
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata

from . import __version__
from .audit import AuditLog
from .config import Thresholds
from .findings import add_findings, doc_evidence, limitation
from .model import Case
from .store import CaseDir, load_case, save_case

STAGE_ORDER = ("read", "classify", "extract", "forensics", "checks", "link", "explain", "crops", "dossier")
_LIBS = ("pymupdf", "rapidocr", "onnxruntime", "numpy", "opencv-python-headless", "pillow", "pydantic")


@dataclass
class Ctx:
    cd: CaseDir
    audit: AuditLog
    th: Thresholds


class _Timeout(Exception):
    pass


def _call_with_timeout(fn: Callable[[], None], timeout: float) -> None:
    """Run fn in a daemon thread. A hung native call cannot be killed: it is abandoned (listed in the limitations)."""
    errors: list[BaseException] = []

    def target() -> None:
        try:
            fn()
        except BaseException as e:  # re-raised below, in the caller's thread
            errors.append(e)

    t = threading.Thread(target=target, daemon=True)  # daemon: a stuck step must not block process exit
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise _Timeout()
    if errors:
        raise errors[0]


def guarded(ctx: Ctx, case: Case, name: str, fn: Callable[[], None], doc_id: str | None = None, *,
            timeout: float | None = None) -> bool:
    """Run one step. A failure or timeout becomes a visible limitation (and an audit event); the case goes on."""
    timeout = ctx.th.stage_timeout_s if timeout is None else timeout
    t0 = time.monotonic()
    try:
        _call_with_timeout(fn, timeout)
        return True
    except _Timeout:
        what = "timed out"
        detail = f"No result after {timeout:g} s. The step was abandoned; its output may be missing or incomplete."
    except Exception as e:
        what, detail = "failed", f"{type(e).__name__}: {e}"[:400]
    ctx.audit.append("system", "stage_failed", {"stage": name, "doc": doc_id, "reason": what, "error": detail,
                                                "seconds": round(time.monotonic() - t0, 3)})
    title = f"Step '{name}' {what}" + (f" for {doc_id}" if doc_id else "")
    add_findings(case, ctx, [limitation(name, title, detail, [doc_evidence(doc_id, f"step {name}")] if doc_id else None)])
    return False


def _stage_fns() -> dict[str, Callable[[Case, Ctx], None]]:
    """The registered stages. Imports are lazy because stage modules import guarded() from here."""
    from .checks import run_checks
    from .read import read_stage
    from .understand.classify import classify_stage
    from .understand.extract import extract_stage
    return {"read": read_stage, "classify": classify_stage, "extract": extract_stage, "checks": run_checks}


def _versions() -> dict[str, str]:
    out = {"python": platform.python_version()}
    for pkg in _LIBS:
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            pass
    return out


def run_case(cd: CaseDir, th: Thresholds | None = None, stages: dict[str, Callable] | None = None) -> Case:
    """Run the stages present, in STAGE_ORDER. `stages` replaces the registered ones (tests inject fakes)."""
    th = th or Thresholds()
    case = load_case(cd)
    ctx = Ctx(cd, AuditLog(cd.audit_path), th)
    fns = _stage_fns() if stages is None else stages
    ctx.audit.append("system", "run_started", {"tool": "docforensics", "version": __version__, "libs": _versions()})
    for name in STAGE_ORDER:
        fn = fns.get(name)
        if fn is None:
            continue
        ctx.audit.append("system", "stage_start", {"stage": name})
        t0 = time.monotonic()
        # a stage may spend up to stage_timeout_s on each document, so the outer limit scales with the case
        ok = guarded(ctx, case, name, lambda fn=fn: fn(case, ctx), timeout=th.stage_timeout_s * (len(case.documents) + 1))
        ctx.audit.append("system", "stage_end", {"stage": name, "ok": ok, "seconds": round(time.monotonic() - t0, 3),
                                                 "tool": "docforensics", "version": __version__})
        save_case(case, cd)
    return case
