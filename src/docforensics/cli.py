"""Command line (design 7.8): run a case, trace a finding to its place in the source file, check the audit trail, serve the review desk.
Everything printed that came from a document goes through quote(): one line, no control or bidi characters."""
import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

from .audit import AuditLog
from .config import Thresholds
from .explain.llm import DEFAULT_MODEL, OllamaClient
from .findings import quote
from .ingest import create_case
from .model import Case, Document, Evidence
from .pipeline import run_case
from .signing import public_key_bytes, signing_view
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


def _llm(args: argparse.Namespace) -> OllamaClient | None:
    """The client for --llm / --llm-model, or None. A run asked to use the model that cannot is stopped here, before anything is made,
    so it is not mistaken for a run that did."""
    if not (args.llm or args.llm_model):
        return None
    model = args.llm_model or DEFAULT_MODEL
    client = OllamaClient(model)
    if not client.digest():  # Ollama lists the models it has; no digest means it is not running, or does not have this one
        name = quote(model, 80)
        raise UsageError(f"the language model {name} is not available from Ollama on this computer. Start Ollama and run: ollama pull {name}")
    return client


def _reading(case: Case, llm: OllamaClient) -> None:
    r = case.reasoning
    if r is None:
        print(f"Language model {quote(llm.model, 80)}: no reading of the case was kept (llm_wording and llm_reasoning in the audit trail say why)")
        return
    print(f"Reading of the case by {quote(r.model, 80)}: inference from the findings above, not a finding and not a verdict")
    if r.summary:
        print(f"  {quote(r.summary, 1200)}")
    for x in r.relations:
        print(f"  {quote(x.a, 20)} and {quote(x.b, 20)} ({quote(x.kind, 20)}): {quote(x.reason, 300)}")
    print("  Reading order: " + ", ".join(quote(i, 20) for i in r.order))


def _run(args: argparse.Namespace) -> int:
    th = _thresholds(args.config)
    llm = _llm(args)
    case, cd, _ = create_case(args.data, _inputs(args.paths, th), th)
    case = run_case(cd, th, llm=llm)
    print(f"Case {case.id}  ({cd.root})")
    for d in case.documents:
        print(f"  {d.id}  {d.doc_type}  {len(d.pages)} page(s)  {quote(d.filename, 80)}")
    print(f"Findings: {len(case.findings)}")
    for f in case.findings:
        print(f"  {f.id}  {f.fclass:<22}  {quote(f.title, 120)}")
    if case.findings:
        print("  " + ", ".join(f"{n} {c}" for c, n in Counter(f.fclass for f in case.findings).items()))
    if llm is not None:
        _reading(case, llm)
    if case.findings:
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
    pinned = None
    if args.pubkey:
        try:
            pinned = public_key_bytes(Path(args.pubkey).read_bytes())
        except (OSError, ValueError) as e:
            raise UsageError(f"cannot read a public key from {args.pubkey}: {e}")
    audit = AuditLog(cd.audit_path)
    ok, bad = audit.verify()
    if not ok:
        print(f"BROKEN at event {bad}: the audit trail of {cd.id} was changed after it was written")
        return 1
    count, head = audit.head()
    if count == 0:  # an empty trail verifies, but every case starts with an event: a missing or emptied file is not a clean one
        print(f"No audit trail: audit.jsonl of {cd.id} is missing or empty")
        return 1
    sig = signing_view(cd, pinned)
    if sig["problem"]:  # the chain holds, but a signature says it is not the trail that was signed
        print(sig["problem"])
        return 1
    print(f"OK: {count} events, head {head}")
    if sig["status"] == "unsigned":
        print("Unsigned: this case has no signed checkpoint. The hash chain shows that the events agree with each other; it does not show "
              "that the end was not cut off, or that the whole trail was not written again.")
        return 0
    late = sig["uncovered"]
    print(f"Signed: {sig['checkpoints']} checkpoint{'s' * (sig['checkpoints'] != 1)} by key {sig['key_id'][:16]}"
          f"{' (the key you gave)' if pinned else ''}, the last covers events 1-{sig['last']['events']}."
          + (f" {late} later event{' is' if late == 1 else 's are'} not covered." if late else "")
          + ("" if pinned else " Compare the key with one you know from elsewhere, or give it with --pubkey."))
    return 0


def _serve(args: argparse.Namespace) -> int:
    import uvicorn  # only this command needs the web stack

    from .web.app import HOST, create_app
    th, llm = _thresholds(args.config), _llm(args)
    print(f"Review desk: http://{HOST}:{args.port}/   (cases are kept in {args.data}; Ctrl+C stops it)")
    uvicorn.run(create_app(Path(args.data), th, llm), host=HOST, port=args.port, log_level="warning")
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
    verify.add_argument("--pubkey", metavar="PEM", help="the public key (a PEM file) that must have signed the case; a case that is unsigned, "
                        "or signed by another key, then fails")
    verify.set_defaults(fn=_verify)
    serve = sub.add_parser("serve", help="open the review desk in a browser (127.0.0.1 only)")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--config", metavar="TOML", help="thresholds to use instead of the defaults")
    serve.set_defaults(fn=_serve)
    for s in (run, serve):
        s.add_argument("--llm", action="store_true", help=f"also use the local language model {DEFAULT_MODEL} through Ollama (its output is "
                       "labelled inference, and it cannot remove or confirm a finding)")
        s.add_argument("--llm-model", metavar="NAME", help="use this Ollama model instead of the default (implies --llm)")
    for s in (run, trace, verify, serve):
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
