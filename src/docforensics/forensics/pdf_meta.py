"""File metadata (design 7.5, D4): the producer and creator the file names, and how long after its creation it was last modified.
A file made by one program and saved by another, or saved long after it was made, may have been changed; the metadata only says
what the file states about itself, and anyone who can write the file can write it."""
import re
from datetime import datetime, timedelta, timezone

from ..findings import doc_evidence, quote
from ..model import Case, Document, Finding
from ..pipeline import Ctx

DETECTOR = "pdf_meta"
_EDITORS = ("acrobat", "photoshop", "illustrator", "gimp", "inkscape", "pdfescape", "sejda", "ilovepdf", "smallpdf", "canva",
            "pdfelement", "foxit", "nitro", "pdf-xchange", "pdf editor", "master pdf")  # names of programs that edit PDF files
_DATE = re.compile(r"D:(\d{4})(\d\d)(\d\d)(\d\d)(\d\d)(\d\d)(?:([Zz])|([+-])(\d\d)'?(\d\d)?'?)?")


def pdf_time(s: str | None) -> datetime | None:
    """A PDF date (D:YYYYMMDDHHMMSS+05'30'), or None when it is missing or not in that form. No zone means UTC."""
    m = _DATE.fullmatch((s or "").strip())
    if not m:
        return None
    y, mo, d, h, mi, sec = map(int, m.groups()[:6])
    try:
        offset = timedelta(hours=int(m[9] or 0), minutes=int(m[10] or 0)) * (-1 if m[8] == "-" else 1)
        return datetime(y, mo, d, h, mi, sec, tzinfo=timezone(offset))
    except ValueError:
        return None


def _length(s: float) -> str:
    d, rest = divmod(int(s), 86400)
    h, rest = divmod(rest, 3600)
    return f"{d} d {h} h {rest // 60} min" if d else f"{h} h {rest // 60} min {rest % 60} s"


def metadata_observations(case: Case, doc: Document, ctx: Ctx) -> list[Finding]:
    th, meta = ctx.th, doc.meta
    where = [doc_evidence(doc.id, "file metadata")]
    out = []
    made, saved = pdf_time(meta.get("creationDate")), pdf_time(meta.get("modDate"))
    if made and saved and (saved - made).total_seconds() > th.mod_after_create_s:
        gap = (saved - made).total_seconds()
        out.append(Finding(fclass="observation", detector=DETECTOR, family="metadata", title="File modified after it was created",
                           detail=f"The file says it was created at {made.isoformat(sep=' ')} and last modified at {saved.isoformat(sep=' ')}, "
                                  f"{_length(gap)} later ({gap:.0f} s). Files modified more than {th.mod_after_create_s} s after their creation are reported.",
                           evidence=where))
    for key in ("producer", "creator"):
        value = meta.get(key) or ""
        if any(re.search(rf"\b{re.escape(w)}", value, re.I) for w in _EDITORS):
            out.append(Finding(fclass="observation", detector=DETECTOR, family="metadata", title=f"File {key} names PDF-editing software",
                               detail=f'The {key} field of the file reads "{quote(value)}". Programs of this kind are used to edit PDF files and also '
                                      f"to make them, so the name alone does not show that the file was edited.",
                               evidence=where))
    return out
