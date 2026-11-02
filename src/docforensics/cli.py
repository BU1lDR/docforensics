"""Command line (design 7.8): run a case, trace a finding to its place in the source file, check the audit trail.
Everything printed that came from a document goes through quote(): one line, no control or bidi characters."""
import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

from .audit import AuditLog
from .config import Thresholds
from .findings import quote
from .ingest import create_case
from .model import Case, Document, Evidence
from .pipeline import run_case
from .store import CaseDir, load_case


class UsageError(Exception):
    """Something the person at the keyboard can fix: a path, a case id, a threshold file."""


def _thresholds(path: str | None) -> Thresholds:
    if not path:
        return Thresholds()
    try:
        return Thresholds.from_toml(path)
    except (OSError, ValueError) as e:
        raise UsageError(f"cannot read thresholds from {path}: {e}")


def _inputs(paths: list[str], th: Thresholds) -> list[tuple[str, bytes]]:
    """Each file named, and the files directly inside each folder named (sub-folders are not entered). A file is read up to one
    byte over the size limit: enough for ingest to refuse it without the whole of a huge file being loaded."""
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files += sorted(q for q in p.iterdir() if q.is_file())
        elif p.is_file():
            files.append(p)
        else:
            raise UsageError(f"not a file or folder: {raw}")
    out = []
    for p in files:
        with p.open("rb") as f:
            out.append((p.name, f.read(th.max_file_bytes + 1)))
    return out


def _case_dir(args: argparse.Namespace) -> CaseDir:
    try:
        return CaseDir.open(args.data, args.case)
    except (ValueError, OSError) as e:
        raise UsageError(f"no such case in {args.data}: {e}")


def _run(args: argparse.Namespace) -> int:
    th = _thresholds(args.config)
    case, cd, _ = create_case(args.data, _inputs(args.paths, th), th)
    case = run_case(cd, th)
    print(f"Case {case.id}  ({cd.root})")
    for d in case.documents:
        print(f"  {d.id}  {d.doc_type}  {len(d.pages)} page(s)  {quote(d.filename, 80)}")
    print(f"Findings: {len(case.findings)}")
    for f in case.findings:
        print(f"  {f.id}  {f.fclass:<22}  {quote(f.title, 120)}")
    if case.findings:
        print("  " + ", ".join(f"{n} {c}" for c, n in Counter(f.fclass for f in case.findings).items()))
        print(f"Follow one to the source file: docforensics trace {case.id} {case.findings[0].id} --data {args.data}")
    return 0 if case.documents else 1


def _integrity(cd: CaseDir, doc: Document) -> str:
    path = (cd.root / doc.stored_path).resolve()
    if not path.is_relative_to(cd.root.resolve()):
        return "(stored path is outside the case folder: not read)"
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "(STORED FILE IS MISSING)"
    return "(stored file matches)" if actual == doc.sha256 else f"(STORED FILE DIFFERS: it hashes to {actual})"


def _location(doc: Document, e: Evidence) -> str:
    if e.page == 0:
        return "the document as a whole"
    dpi = doc.pages[e.page - 1].dpi if 0 < e.page <= len(doc.pages) else 200
    px = " ".join(f"{v:.1f}" for v in e.box)
    pt = " ".join(f"{v * 72 / dpi:.1f}" for v in e.box)
    return f"page {e.page}, box {px} px at {dpi} dpi = {pt} pt"


def _trace(args: argparse.Namespace) -> int:
    cd = _case_dir(args)
    try:
        case: Case = load_case(cd)
    except (ValueError, OSError) as e:
        raise UsageError(f"cannot read case {cd.id}: {e}")
    f = next((f for f in case.findings if f.id == args.finding), None)
    if f is None:
        raise UsageError(f"case {case.id} has no finding {quote(args.finding, 40)!r}")
    docs = {d.id: d for d in case.documents}
    print(f"{f.id}  {f.fclass}  {quote(f.detector, 60)}  {quote(f.title, 160)}")
    if f.detail:
        print(f"  {quote(f.detail, 400)}")
    if not f.evidence:
        print("  (no evidence recorded)")
    for i, e in enumerate(f.evidence, 1):
        print(f"evidence {i}: {quote(e.note, 120) or '-'}")
        doc = docs.get(e.doc)
        if doc is None:
            print(f"  document {quote(e.doc, 20)}: not in this case")
            continue
        print(f"  document {doc.id}: {quote(doc.filename, 120)}")
        print(f"  stored file: {doc.stored_path}")
        print(f"  sha256: {doc.sha256} {_integrity(cd, doc)}")
        print(f"  location: {_location(doc, e)}")
        if e.value is not None:
            print(f"  value: {quote(e.value, 200)}")
        if e.crop_path:
            print(f"  crop: {e.crop_path}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    cd = _case_dir(args)
    audit = AuditLog(cd.audit_path)
    ok, bad = audit.verify()
    if not ok:
        print(f"BROKEN at event {bad}: the audit trail of {cd.id} was changed after it was written")
        return 1
    count, head = audit.head()
    if count == 0:  # an empty trail verifies, but every case starts with an event: a missing or emptied file is not a clean one
        print(f"No audit trail: audit.jsonl of {cd.id} is missing or empty")
        return 1
    print(f"OK: {count} events, head {head}")
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="docforensics", description="Document forensics: findings for a human reviewer, each traced to its source.")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="analyse documents as one case")
    run.add_argument("paths", nargs="+", metavar="PATH", help="a file, or a folder (the files directly inside it)")
    run.add_argument("--config", metavar="TOML", help="thresholds to use instead of the defaults")
    run.set_defaults(fn=_run)
    trace = sub.add_parser("trace", help="show where a finding's evidence is in the source file")
    trace.add_argument("case")
    trace.add_argument("finding")
    trace.set_defaults(fn=_trace)
    verify = sub.add_parser("verify-audit", help="check that a case's audit trail has not been changed")
    verify.add_argument("case")
    verify.set_defaults(fn=_verify)
    for s in (run, trace, verify):
        s.add_argument("--data", default="data", metavar="DIR", help="where cases are kept (default: data)")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):  # a console that cannot show a character gets '?', not a crash
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    try:
        return args.fn(args)
    except (UsageError, OSError) as e:
        print(f"docforensics: {e}", file=sys.stderr)
        return 2
