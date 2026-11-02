"""Revision-diff detector (design 7.5). A PDF saved incrementally keeps every earlier revision inside the file, each ending at
its own `%%EOF`. Cutting the file at each of those ends gives the document as it stood at that save; the words of two
consecutive revisions are compared and what differs is reported as an observation. The file says that text was changed
after an earlier save, not whether the change was proper."""
import re
from difflib import SequenceMatcher

import pymupdf

from ..config import Thresholds
from ..findings import doc_evidence, limitation, quote
from ..model import Box, Case, Document, Evidence, Finding, Word
from ..pipeline import Ctx
from ..read.pdf import page_words

DETECTOR = "pdf_revisions"
_END = re.compile(rb"startxref\s{1,16}(\d{1,12})\s{1,16}%%EOF")  # bounded runs: a hostile file cannot make a match slow
_XREF = re.compile(rb"\s{0,16}(?:xref|\d{1,10}\s{1,8}\d{1,5}\s{1,8}obj)")  # a classic table, or the object of an xref stream


def revision_ends(data: bytes) -> list[int]:
    """Where each saved revision ends: the end of every `startxref <offset> %%EOF` whose offset points at a cross-reference
    table or stream earlier in the file. Page text that merely reads like a trailer does not point at one."""
    return [m.end() for m in _END.finditer(data) if int(m[1]) < m.start() and _XREF.match(data, int(m[1]))]


def _reading_order(words: list[Word]) -> list[Word]:
    """Line by line, left to right. A word written by a later save sits at the end of the content stream wherever it is
    drawn, so the stream order cannot be compared as it stands."""
    out: list[Word] = []
    line: list[Word] = []
    top = 0.0
    for w in sorted(words, key=lambda w: w.box[1] + w.box[3]):
        mid = (w.box[1] + w.box[3]) / 2
        if line and mid - top > (w.box[3] - w.box[1]) / 2:
            out += sorted(line, key=lambda v: v.box[0])
            line = []
        if not line:
            top = mid
        line.append(w)
    return out + sorted(line, key=lambda v: v.box[0])


def _revision_words(raw: bytes, doc: Document, th: Thresholds) -> list[list[Word]]:
    """The words of each page of one revision, in the pixels of the page as the reader rendered it."""
    with pymupdf.open(stream=raw, filetype="pdf") as pdf:
        return [_reading_order(page_words(pdf[i], f"p{i + 1}", (doc.pages[i].dpi if i < len(doc.pages) else 200) / 72))
                for i in range(min(pdf.page_count, th.max_pages))]


def _changes(old: list[str], new: list[str]) -> list[tuple[str, int, int, int, int]]:
    """The stretches where two word lists differ, as (tag, old start, old end, new start, new end)."""
    n = min(len(old), len(new))
    lo = 0
    while lo < n and old[lo] == new[lo]:
        lo += 1
    hi = 0
    while hi < n - lo and old[-1 - hi] == new[-1 - hi]:
        hi += 1
    sm = SequenceMatcher(None, old[lo:len(old) - hi], new[lo:len(new) - hi], autojunk=False)  # junk heuristics drop common words
    return [(t, i1 + lo, i2 + lo, j1 + lo, j2 + lo) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]


def _union(words: list[Word]) -> Box:
    return (min(w.box[0] for w in words), min(w.box[1] for w in words), max(w.box[2] for w in words), max(w.box[3] for w in words))


def _evidence(doc: Document, r: int, tag: str, page: int, before: list[Word], after: list[Word]) -> Evidence:
    """Where a change is: removed text is pointed out where it stood in the earlier revision, the rest where it is now."""
    words = before if tag == "delete" else after
    note = f"where this text stood in revision {r - 1}" if tag == "delete" else f"the text as it stands in revision {r}"
    return Evidence(doc=doc.id, page=page, box=_union(words), note=note, value=quote(" ".join(w.text for w in words)))


def _finding(doc: Document, r: int, tag: str, page: int, before: list[Word], after: list[Word]) -> Finding:
    was, now = quote(" ".join(w.text for w in before)), quote(" ".join(w.text for w in after))
    if tag == "insert":
        what, detail = "added", f'The text "{now}" is in revision {r} and was not in revision {r - 1}.'
    elif tag == "delete":
        what, detail = "removed", f'The text "{was}" stood in revision {r - 1} and is not in revision {r}.'
    else:
        what, detail = "changed", f'In revision {r - 1} the text read "{was}"; in revision {r} it reads "{now}".'
    return Finding(fclass="observation", detector=DETECTOR, family="metadata", title=f"Text {what} in revision {r} (page {page})",
                   detail=detail, evidence=[_evidence(doc, r, tag, page, before, after)])


def _compare(doc: Document, r: int, old: list[list[Word]], new: list[list[Word]], th: Thresholds, issues: list[str]) -> list[Finding]:
    """What the save that made revision r changed in the text of the pages: one finding per changed stretch, or one for the
    lot when there are more than max_revision_runs of them."""
    runs = []  # (tag, page, words before, words after)
    for p in range(1, max(len(old), len(new)) + 1):
        if p <= len(doc.pages) and doc.pages[p - 1].read_mode == "ocr":
            continue  # a scanned page has no text layer to compare
        before, after = (old[p - 1] if p <= len(old) else []), (new[p - 1] if p <= len(new) else [])
        if max(len(before), len(after)) > th.max_diff_words:
            issues.append(f"page {p} has {max(len(before), len(after))} words, over the {th.max_diff_words} compared between "
                          f"revision {r - 1} and revision {r}")
            continue
        runs += [(tag, p, before[i1:i2], after[j1:j2])
                 for tag, i1, i2, j1, j2 in _changes([w.text for w in before], [w.text for w in after])]
    if len(runs) <= th.max_revision_runs:
        return [_finding(doc, r, *run) for run in runs]
    pages = sorted({run[1] for run in runs})
    where = f"page {pages[0]}" if len(pages) == 1 else "pages " + ", ".join(map(str, pages))
    return [Finding(fclass="observation", detector=DETECTOR, family="metadata", title=f"{len(runs)} text changes in revision {r}",
                    detail=f"{len(runs)} separate changes were made to the text of {where} between revision {r - 1} and "
                           f"revision {r}, more than the {th.max_revision_runs} that are listed one by one. The first "
                           f"{th.max_revision_runs} are marked as evidence.",
                    evidence=[_evidence(doc, r, *run) for run in runs[: th.max_revision_runs]])]


def revision_diff(case: Case, doc: Document, ctx: Ctx) -> list[Finding]:
    th = ctx.th
    data = (ctx.cd.root / doc.stored_path).read_bytes()
    whole = [doc_evidence(doc.id, "revision history")]
    if b"/Linearized" in data[:1024]:  # no linearized fixture can be made here (PyMuPDF dropped it), so no claim is made
        return [limitation(DETECTOR, "Linearized PDF: revisions not compared",
                           "This file is linearized (arranged for fast web viewing). Comparing its saved revisions is not "
                           "supported, so any text changed by a later save would not be shown.", whole)]
    ends = revision_ends(data)
    if not ends:
        return [limitation(DETECTOR, "PDF revisions not compared",
                           "The file has no end-of-file marker that points at a cross-reference table, so its saved revisions "
                           "could not be told apart.", whole)]
    if len(ends) > th.max_revisions:
        return [limitation(DETECTOR, "Too many PDF revisions to compare",
                           f"The file holds {len(ends)} saved revisions; only files with at most {th.max_revisions} are opened, "
                           "so none were compared.", whole)]
    issues: list[str] = []
    if data[ends[-1]:].strip():
        issues.append(f"{len(data[ends[-1]:].strip())} bytes follow the last end-of-file marker and were not examined")
    out: list[Finding] = []
    prev = None
    for r, end in enumerate(ends if len(ends) > 1 else [], 1):  # one revision has nothing to be compared with
        try:
            words = _revision_words(data[:end], doc, th)
        except Exception as e:
            issues.append(f"revision {r} could not be opened ({type(e).__name__})")
            prev = None
            continue
        if prev is not None:
            out += _compare(doc, r, prev, words, th, issues)
        prev = words
    if issues:
        shown = issues[:10] + ([f"and {len(issues) - 10} more"] if len(issues) > 10 else [])
        out.append(limitation(DETECTOR, "Revision history only partly analysed",
                              "Some of this file's revision history could not be examined: " + "; ".join(shown) + ".", whole))
    return out
