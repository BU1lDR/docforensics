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
    ("pdf_overlay", "observation"): (
        "The file draws a filled shape or a picture over text that is still stored in the file, or it stores text in a way that "
        "keeps it from being seen (invisible, too small to read, or outside the page). Panels, redactions, logos, stamps and "
        "forms being filled in all do this, and so does a figure that was covered and typed over. The file does not say which.",
        ["Compare the marked place on the page with the text that lies under it.",
         "Check whether the covered text is a figure, date or name that other findings depend on.",
         "Ask the issuer for a copy sent directly by them and compare it with this one."]),
    ("pdf_overlay", "processing_limitation"): (
        f"{_LIMIT} Some pages could not be examined for text under shapes or pictures, or for hidden text, so such content may "
        "exist and would not have been shown.",
        _UNCHECKED),
    ("pdf_fonts", "observation"): (
        "A figure or date is set in a different font, size or colour from the figures beside it. Documents are often put together "
        "by more than one program, and a total or a note may be set differently on purpose, so this has ordinary causes. Font names "
        "are those the file gives: two faces that look alike to the eye, such as Arial and Helvetica, have different names.",
        ["Compare the marked value with its neighbours on the page.",
         "Check whether the value is one that other findings depend on, such as a balance, a salary or a date."]),
    ("pdf_fonts", "processing_limitation"): (
        f"{_LIMIT} Some pages could not be compared in full for the fonts of their figures, so a figure set in a different font "
        "may exist and would not have been shown.",
        _UNCHECKED),
    ("pdf_meta", "observation"): (
        "The file's own record of how it was made, which program is named as its producer or creator and when it was created and "
        "last modified, shows something the reviewer may want to know. Saving a file again is common and harmless, and anyone who "
        "can write the file can write this record, so it neither proves nor rules out a change to the content.",
        ["Ask the issuer how and when the document was made and whether it was saved again.",
         "Compare the dates in the file record with the dates printed on the document."]),
    ("scan_noise", "observation"): (
        "Some words on a scanned page have a different image grain from the rest of the page: less where paper was filled in or "
        "smoothed, more where a piece came from a scan made differently. Uneven lighting, a second JPEG save, a stamp or a fold can "
        "change the grain as well, so this has ordinary causes and does not show what was done.",
        ["Look at the marked words in the original picture, at full size, beside their neighbours.",
         "Ask the issuer for the original document or another scan of the same page."]),
    ("scan_noise", "processing_limitation"): (
        f"{_LIMIT} The image grain of some scanned words could not be compared, so a changed word may exist among them and would "
        "not have been shown.",
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
    ("payslip_sums", "inconsistency"): (
        "Totals printed on the payslip do not agree with each other, or with the lines listed under them, by more than the "
        "stated tolerance. An edited figure would cause this, and so would a misread digit, a line that was not read, or a "
        "layout these checks do not assume.",
        ["Compare the marked cells with the page, digit by digit.",
         "Add the lines up by hand and work the net pay out from the two totals.",
         "If the difference holds, ask the employer for a payslip issued directly."]),
    ("payslip_sums", "processing_limitation"): (
        f"{_LIMIT} The totals could not be checked here, or a difference was found that could not be trusted because a figure "
        "was unreadable or read with low confidence. Whether the payslip adds up is unknown.",
        _UNCHECKED),
    ("payslip_words", "inconsistency"): (
        "The net pay written in words and the net pay in figures differ by more than the stated tolerance. An edited figure or "
        "edited words would cause this, and so would a misread digit or word.",
        ["Compare the figure and the words with the page.",
         "If they differ, ask the employer which of the two is meant."]),
    ("payslip_words", "processing_limitation"): (
        f"{_LIMIT} The amount in words could not be compared with the figure here, or a difference was found that could not be "
        "trusted because one of them was unreadable or read with low confidence. Whether they agree is unknown.",
        _UNCHECKED),
    ("payslip_dates", "inconsistency"): (
        "The pay date falls outside the pay month and the month after it. A late or early payroll run would cause this, and so "
        "would a changed date or month, a misread digit, or a date written in a different convention (dates are read day first, "
        "DD/MM/YYYY).",
        ["Compare the pay date and the pay month with the page.",
         "Check the payment against the bank statement, which records when the salary arrived."]),
    ("payslip_dates", "processing_limitation"): (
        f"{_LIMIT} The pay date could not be compared with the pay month here, or a difference was found that could not be "
        "trusted because a date was unreadable, ambiguous or read with low confidence. Whether they agree is unknown.",
        _UNCHECKED),
    ("application_dates", "inconsistency"): (
        "The weekday printed with the application date is not the weekday that date fell on. A slip when the form was filled "
        "in would cause this, and so would a changed date or weekday, or a misread digit.",
        ["Compare the date and the weekday with the page.",
         "Ask the applicant or the lender for the date the application was received."]),
    ("application_dates", "processing_limitation"): (
        f"{_LIMIT} The weekday could not be compared with the date here, or a difference was found that could not be trusted "
        "because the date was unreadable, ambiguous or read with low confidence. Whether they agree is unknown.",
        _UNCHECKED),
}


def _across(detector: str, differs: str, steps: list[str], unknown: str) -> dict[tuple[str, str], tuple[str, list[str]]]:
    """The two entries every check across documents needs: what a difference may mean, and what an unreadable input leaves unknown."""
    return {(detector, "inconsistency"): (differs, steps), (detector, "processing_limitation"): (f"{_LIMIT} {unknown}", _UNCHECKED)}


TEMPLATES.update(_across(
    "cross_name",
    "The name read from two or more documents is not the same by the measure the finding states. A different person would cause "
    "this, and so would a name written another way that the comparison does not recognise (a spelling, a nickname, an "
    "abbreviation), or a misread letter.",
    ["Compare the marked names with each page.",
     "Confirm the spelling with the issuer of the document that differs."],
    "The names could not be compared here, or a difference was found that could not be trusted because a name was unreadable or "
    "read with low confidence. Whether the names agree is unknown."))
TEMPLATES.update(_across(
    "cross_address",
    "The address read from two or more documents is not the same by the measure the finding states: the text is not alike enough, "
    "or a number in it (a flat, house or postal number) differs. A move would cause this, and so would an older address on a "
    "re-issued document, an address written another way, or a misread digit.",
    ["Compare the marked addresses with each page, number by number.",
     "Ask which address is current and confirm it with the issuer."],
    "The addresses could not be compared here, or a difference was found that could not be trusted because an address was "
    "unreadable or read with low confidence. Whether the addresses agree is unknown."))
TEMPLATES.update(_across(
    "cross_employer",
    "The employer named in two or more documents is not the same by the measure the finding states. Words such as Pvt and Ltd "
    "are ignored. A change of employer would cause this, and so would a trading name or abbreviation in one document and the "
    "registered name in another, or a misread word.",
    ["Compare the marked employer names with each page.",
     "Ask the employer which name it uses for payroll."],
    "The employer names could not be compared here, or a difference was found that could not be trusted because a name was "
    "unreadable or read with low confidence. Whether they agree is unknown."))
TEMPLATES.update(_across(
    "cross_account",
    "The account numbers read from two or more documents do not match. A masked number matches when its visible end (at least "
    "three characters) is the end of the other number. A different account would cause this, and so would a misread digit.",
    ["Compare the marked account numbers with each page, digit by digit.",
     "Confirm the account with the bank."],
    "The account numbers could not be compared here, or a difference was found that could not be trusted because a number was "
    "unreadable or read with low confidence. Whether they agree is unknown."))
TEMPLATES.update(_across(
    "cross_payer",
    "None of the salary or payroll credits on the bank statement names a payer that shares a word with the employer named in the "
    "other document. A different employer would cause this, and so would a payer written another way (a trading name, an "
    "abbreviation, a group company), a payer the statement does not name, or a misread word. The comparison is a heuristic.",
    ["Compare the employer and the credit descriptions with each page.",
     "Ask the employer which legal name pays the salary."],
    "The employer could not be compared with the payer of the salary here, or a difference was found that could not be trusted "
    "because a word was unreadable or read with low confidence. Whether they agree is unknown."))
TEMPLATES.update(_across(
    "cross_net_pay",
    "The net pay on the payslip is not found among the credits on the bank statement for the month it was paid, within the "
    "stated tolerance. A different amount paid would cause this, and so would a payslip whose figures were changed together, a "
    "part payment or a payment in several credits, a payslip that does not belong to this account, or a misread digit.",
    ["Compare the net pay and the nearest credit with each page, digit by digit.",
     "Ask the employer for the payment record and the bank for a statement issued directly."],
    "The net pay could not be matched to a credit here, or a difference was found that could not be trusted because a figure "
    "was unreadable or read with low confidence. Whether the payslip and the statement agree is unknown."))
TEMPLATES.update(_across(
    "cross_income",
    "The monthly income declared on the application differs from the gross earnings on the payslip by more than the stated "
    "tolerance. A changed figure in either document would cause this, and so would income from another source that the "
    "application includes, a different month, or a misread digit.",
    ["Compare the declared income and the gross earnings with each page.",
     "Ask the applicant how the declared income is made up."],
    "The declared income could not be compared with the gross earnings here, or a difference was found that could not be trusted "
    "because a figure was unreadable or read with low confidence. Whether they agree is unknown."))
TEMPLATES.update(_across(
    "cross_dates",
    "One or more documents are dated after the application they were submitted with. A wrongly entered or changed date would "
    "cause this, and so would an application filled in earlier than it was submitted, a document re-issued afterwards, a date "
    "written in a different convention (dates are read day first, DD/MM/YYYY), or a misread digit.",
    ["Compare the marked dates with each page.",
     "Ask the applicant and the lender when each document was received."],
    "The dates could not be compared here, or a difference was found that could not be trusted because a date was unreadable, "
    "ambiguous or read with low confidence. Whether the documents are dated in order is unknown."))
TEMPLATES.update({
    ("cross_duplicate", "observation"): (
        "The same file was submitted more than once, with identical content. It may be an accidental second upload, or one document "
        "offered in two roles. The tool does not say which.",
        ["Check whether the document was meant to appear more than once.",
         "Remove the extra copy and run the case again if it was not."]),
    ("cross_producer", "observation"): (
        "Documents of different kinds name the same producing software and were created within a few minutes of each other. "
        "Ordinary workflows do this too: one office system issuing both, or one print-to-PDF tool used for everything. On its own "
        "it is a pointer for the reviewer, not a conclusion about the documents.",
        ["Ask where each document came from and how it reached the applicant.",
         "Weigh it together with any other findings that cite the same documents."]),
    ("cross_checks", "processing_limitation"): (
        f"{_LIMIT} Some comparisons across documents could not be made, because a document was not submitted, was not recognised or "
        "could not be read, or because a date or value they depend on was unavailable. What those comparisons would have shown is "
        "unknown.",
        _UNCHECKED),
    ("context_emi", "observation"): (
        "The monthly obligations on the application are a larger share of the declared income than the reference limit the finding "
        "states. That limit is a synthetic, illustrative value, not a lending standard, and interest is ignored. Many ordinary "
        "applications are above such a limit.",
        ["Check the declared income, the existing instalments, the loan amount and the tenure against the page.",
         "Treat it as context for the reviewer's own assessment."]),
    ("context_emi", "processing_limitation"): (
        f"{_LIMIT} The rule on monthly obligations could not be applied, because a figure it needs was unreadable, read with low "
        "confidence, or not a usable number. Whether the obligations are within the reference limit is unknown.",
        _UNCHECKED),
    ("context_age", "observation"): (
        "A document is dated further before the application than the reference limit the finding states. That limit is a "
        "synthetic, illustrative value, not a lending standard. Documents are often older for ordinary reasons, such as a "
        "statement kept from an earlier month.",
        ["Check the date of the document against the page.",
         "Ask for a more recent document if the lender requires one."]),
})


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
