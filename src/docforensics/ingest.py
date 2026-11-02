"""Ingest: type by magic bytes, size and page limits, storage by hash. A bad file becomes a limitation, never a crash."""
import hashlib
import os
import re
import stat
from datetime import datetime, timezone

import pymupdf

from .audit import AuditLog
from .config import Thresholds
from .findings import add_findings, limitation
from .model import Case, Document
from .pipeline import Ctx
from .store import CaseDir, save_case

_EXT = {"pdf": "pdf", "png": "png", "jpeg": "jpg"}


def sniff(data: bytes) -> str | None:
    """File type from the first bytes. The extension is never consulted."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return None


def _safe_name(name: str) -> str:
    """The name is display text only (never a path), but keep control characters out of logs and terminals."""
    return re.sub(r"[\x00-\x1f\x7f]", "?", name)[:200]


def _pdf_problem(data: bytes, th: Thresholds) -> str | None:
    unreadable = "corrupt or unreadable PDF"
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        return unreadable
    try:
        if doc.needs_pass:
            return "encrypted PDF (password required)"
        n = doc.page_count
    except Exception:
        return unreadable
    finally:
        doc.close()
    if n == 0:
        return f"{unreadable} (no pages found)"
    if n > th.max_pages:
        return f"too many pages ({n}; limit {th.max_pages})"
    return None


def create_case(data_root, files: list[tuple[str, bytes]], th: Thresholds) -> tuple[Case, CaseDir, AuditLog]:
    cd = CaseDir.create(data_root)
    audit = AuditLog(cd.audit_path)
    case = Case(id=cd.id, created=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    ctx = Ctx(cd, audit, th)
    audit.append("system", "case_created", {"case": case.id, "thresholds": th.as_dict()})
    for filename, data in files:
        name, kind = _safe_name(filename), sniff(data)
        if not data:
            reason = "empty file"
        elif len(data) > th.max_file_bytes:
            reason = f"file too large ({len(data)} bytes; limit {th.max_file_bytes})"
        elif kind is None:
            reason = "unsupported file type (only PDF, PNG and JPEG are read)"
        elif len(case.documents) >= th.max_docs:
            reason = f"document limit reached ({th.max_docs} per case)"
        else:
            reason = _pdf_problem(data, th) if kind == "pdf" else None
        if reason:
            audit.append("system", "file_rejected", {"filename": name, "size": len(data), "reason": reason})
            add_findings(case, ctx, [limitation("ingest", f"File not ingested: {reason}", f"{name}: {reason}")])
            continue
        sha = hashlib.sha256(data).hexdigest()
        rel = f"files/{sha}.{_EXT[kind]}"
        path = cd.root / rel
        if not path.exists():  # the same file twice shares one stored copy
            path.write_bytes(data)
            os.chmod(path, stat.S_IREAD)
        doc = Document(id=f"D{len(case.documents) + 1}", sha256=sha, filename=name, stored_path=rel, size=len(data),
                       kind="unknown" if kind == "pdf" else "image")
        case.documents.append(doc)
        audit.append("system", "file_ingested", {"doc": doc.id, "filename": name, "sha256": sha, "size": len(data), "type": kind})
    save_case(case, cd)
    return case, cd, audit
