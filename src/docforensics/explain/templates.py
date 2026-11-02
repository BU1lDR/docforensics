"""Explanation templates (design 7.6). The wording is fixed per detector and class. A finding adds to it only where its evidence
is (document ids, page numbers, a count) and how doubtful its weakest reading is, so text taken from a document never reaches
an explanation. Wording states what was measured and what else could cause it; it never says what happened. A later task that
adds a detector adds its entries here; a detector with none falls back on the entry for its class."""
from ..model import Case, Finding

_LIMIT = "This is a limit of the analysis, not a finding about the document."
_UNCHECKED = [
    "Treat what this step would have shown as not checked, not as clear.",
    "Compare the document yourself for what the step was meant to examine, or supply a clearer copy and run the case again.",
]

# (detector, class) -> (text, next steps). Detector "*" is the fallback for the class.
TEMPLATES: dict[tuple[str, str], tuple[str, list[str]]] = {
    ("*", "observation"): (
        "The tool saw this and recorded it. It is an observation, not a problem: unaltered documents can show the same thing.",
        ["Decide whether this is normal for this kind of document and for where it came from."]),
    ("*", "inconsistency"): (
        "Two things that should agree do not, by the measure the finding states. The measure uses what was read from the page, "
        "and a misreading can produce the same difference as a changed value.",
        ["Open each piece of evidence and compare it with the page.",
         "If the difference holds, check it against the issuer's own record."]),
    ("*", "potential_manipulation"): (
        "Independent kinds of check point at the same place in the document. That makes the place worth a closer look. It is a "
        "priority for a reviewer, not a probability and not a conclusion about what happened.",
        ["Go through the evidence one piece at a time.",
         "Look for an ordinary explanation for each piece before drawing any conclusion, and verify with the issuer where a figure is in doubt."]),
    ("*", "processing_limitation"): (
        f"{_LIMIT} A step could not run in full, or its result could not be trusted, so what it would have shown is unknown.",
        _UNCHECKED),
    ("pdf_revisions", "observation"): (
        "The PDF file still holds an earlier saved version of itself, and the text differs between that version and a later one. "
        "Later saves have ordinary causes, such as a correction, a re-issue or a form being filled in, as well as improper ones. "
        "The file does not say which.",
        ["Ask the issuer for a copy sent directly by them and compare it with this one.",
         "Check whether the changed text is a figure, date or name that other findings depend on."]),
    ("pdf_revisions", "processing_limitation"): (
        f"{_LIMIT} The saved revisions of this PDF could not be compared in full, so a change made by a later save may exist "
        "and would not have been shown.",
        _UNCHECKED),
    ("statement_balance", "inconsistency"): (
        "The running balance printed on the statement does not follow from the amounts printed on its rows, by more than the "
        "stated tolerance. An edited figure would cause this, and so would a misread digit, a row that was not read, or a layout "
        "these checks do not assume.",
        ["Compare the marked cells with the page, digit by digit.",
         "Work the balance out by hand from the last row before the break.",
         "If the break holds, ask the bank for a statement issued directly."]),
    ("statement_balance", "processing_limitation"): (
        f"{_LIMIT} The balance column could not be checked here, or a difference was found that could not be trusted because a "
        "figure was unreadable, read with low confidence, or laid out in a way the check does not assume. Whether the balances "
        "add up is unknown.",
        _UNCHECKED),
    ("statement_dates", "inconsistency"): (
        "A date on the statement falls out of order, or outside the period the statement itself states. Dates are read day first "
        "(DD/MM/YYYY), so a different convention in the source would give the same result.",
        ["Compare the marked date with the page.",
         "Check the convention the statement uses for dates and the period it covers."]),
    ("statement_dates", "processing_limitation"): (
        f"{_LIMIT} The dates could not be checked here, or a difference was found that could not be trusted because a date was "
        "unreadable, ambiguous or read with low confidence. Whether the dates are in order is unknown.",
        _UNCHECKED),
}


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _where(f: Finding) -> str:
    """Where the evidence is, from ids, page numbers and a count: 'It cites 4 places in D1 (pages 1, 2) and D2 (whole document).'"""
    if not f.evidence:
        return ""
    pages: dict[str, set[int]] = {}
    for e in f.evidence:
        pages.setdefault(e.doc, set()).add(e.page)
    named = []
    for doc, ps in pages.items():
        real = sorted(p for p in ps if p > 0)
        bits = ([("page " if len(real) == 1 else "pages ") + ", ".join(map(str, real))] if real else []) + (["whole document"] if 0 in ps else [])
        named.append(f"{doc} ({' and '.join(bits)})")
    n = len(f.evidence)
    return f"It cites {n} {'place' if n == 1 else 'places'} in {_join(named)}."


def explain_finding(f: Finding, case: Case) -> tuple[str, list[str]]:
    """(explanation, next steps) for one finding."""
    body, steps = TEMPLATES.get((f.detector, f.fclass)) or TEMPLATES[("*", f.fclass)]
    doubt = f"The weakest reading behind it has confidence {f.conf:.2f} (on a scale of 0 to 1)." \
        if f.fclass in ("inconsistency", "potential_manipulation") and f.conf < 1.0 else ""
    return " ".join(s for s in (body, _where(f), doubt) if s), list(steps)
