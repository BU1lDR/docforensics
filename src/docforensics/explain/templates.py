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
    ("file_structure", "observation"): (
        "The stored bytes of the file show a structural fact: extra bytes after the end of the file, records inside it that disagree with "
        "each other, a signed range that stops before the end, an embedded file or an action key, an index that had to be rebuilt, or an "
        "editing program named in a picture's own metadata. Files from ordinary programs can show each of these, and anyone who can write "
        "the file can write them, so the observation neither proves nor rules out a change to the content. The tool reads positions and "
        "names only: it does not check a signature, open an embedded file, run an action or look for malware.",
        ["Ask the issuer how the file was made and for a copy sent directly by them.",
         "Compare what the file states, such as the dates and the program named, with what you know of the document."]),
    ("file_structure", "processing_limitation"): (
        f"{_LIMIT} The raw structure of this file could not be examined in full, or a part of it (a signature, an XMP packet, the end of "
        "an image) was not checked, so a fact about the file's bytes may exist and would not have been shown.",
        _UNCHECKED),
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
    ("scan_grain", "processing_limitation"): (
        f"{_LIMIT} The picture of a scanned page has no scanner grain on its paper, as a page printed or rendered to an image has none, "
        "and the checks of image grain, of placement and of learned word measures were built on scans that do. They were not applied to "
        "that page, so a changed word may exist there and would not have been shown. A scan that is very clean or cut at white may be "
        "taken for such a page.",
        _UNCHECKED),
    ("scan_layout", "observation"): (
        "Some words on a scanned page sit out of line with the text around them: a word higher or lower than the rest of its row, a "
        "figure whose right edge does not line up with its column, or a figure of another size than the page's other figures. A piece "
        "taken from a scan that was turned differently, or text typed over an erased place, would look like this. A crease, a curled "
        "page or a misread box would too, so this has ordinary causes and does not show what was done.",
        ["Look at the marked words in the original picture, at full size, with a straight edge along the row or the column.",
         "Ask the issuer for the original document or another scan of the same page."]),
    ("scan_layout", "processing_limitation"): (
        f"{_LIMIT} The placement of some scanned words could not be compared, so a word set out of line may exist among them and "
        "would not have been shown.",
        _UNCHECKED),
    ("ela", "observation"): (
        "The picture of this scanned page was saved as a JPEG more than once. Most of its ink still carries a mark of the earlier "
        "save, and the highlighted places do not: they behave as if they had been added after it. A piece pasted in from another "
        "picture, or text typed into the scan, would look like this. So would a page put together from more than one scan, or a "
        "stamp, a date, a page number or a sticker that the scanner or a program added later. "
        "This has ordinary causes and does not show what was done.",
        ["Look at the marked places in the original picture, at full size, beside their neighbours.",
         "Ask how the page was scanned and saved, and ask the issuer for the original document or another scan of the same page."]),
    ("ela", "processing_limitation"): (
        f"{_LIMIT} The history of JPEG saves of some scanned pages was not examined, because the page is not a JPEG picture, was "
        "scaled or turned when it was read, or could not be read. A piece added after an earlier save may exist there and would not "
        "have been shown.",
        _UNCHECKED),
    ("learned_patches", "observation"): (
        "Some words on a scanned page differ from the other words of the same page in the way edited words differed in the data this check "
        "was fitted to: a weighted sum of fourteen measures (grain, edges, strokes, ink, JPEG blocks, baseline, placement, and how far a "
        "word sits off the line of its neighbours) reached the limit set on that data. The weights were fitted to synthetic edits made by "
        "this project's own generator, so the score says how much a word looks like those, not that anything was changed. Uneven lighting, "
        "a stamp, a fold, a second JPEG save, a different typeface or a field filled in by another program move the same measures, so this "
        "has ordinary causes and does not show what was done.",
        ["Look at the marked words in the original picture, at full size, beside their neighbours.",
         "Ask the issuer for the original document or another scan of the same page."]),
    ("learned_patches", "processing_limitation"): (
        f"{_LIMIT} The learned measures could not be applied to some scanned pages (the page is of poor quality, or too few of its words "
        "could be measured), so a changed word may exist there and would not have been shown.",
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


TEMPLATES.update({
    ("cross_name", "observation"): (
        "The name in two or more documents has the same words written differently: in another order, with a title added or left "
        "out, or with an initial standing for a name. People write their own name in different ways on different documents, so "
        "this has ordinary causes. The tool records it because the documents do not carry the name in one form.",
        ["Compare the marked names with each page.",
         "Check that an initial stands for the same name in both documents."]),
    ("cross_address", "observation"): (
        "The address in two or more documents has the same parts in another order. Addresses are often laid out in a different "
        "order on different documents, so this has ordinary causes. The tool records it because the documents do not carry the "
        "address in one form.",
        ["Compare the marked addresses with each page, part by part.",
         "Check that the numbers belong to the same parts in both."]),
    ("cross_employer", "observation"): (
        "The employer named in two or more documents is the same apart from its legal form (words such as Pvt, Ltd, Private or "
        "Limited, present in one and left out or spelt another way in another). Companies are often written with or without it, "
        "so this has ordinary causes.",
        ["Compare the marked employer names with each page.",
         "Check that the document is not naming a different company with the same core name."]),
})
TEMPLATES.update(_across(
    "cross_name",
    "The name read from two or more documents is not the same by the measure the finding states. A different person would cause "
    "this, and so would a name written another way that the comparison does not recognise (a spelling, a nickname, an "
    "abbreviation, a word left out), or a misread letter. A finding titled 'Minor mismatch' is a near miss: names that are close "
    "but not identical, which a typing slip or a misread letter would also give.",
    ["Compare the marked names with each page.",
     "Confirm the spelling with the issuer of the document that differs."],
    "The names could not be compared here, or a difference was found that could not be trusted because a name was unreadable or "
    "read with low confidence. Whether the names agree is unknown."))
TEMPLATES.update(_across(
    "cross_address",
    "The address read from two or more documents is not the same by the measure the finding states: the text is not alike enough, "
    "or a number in it (a flat, house or postal number) differs. A move would cause this, and so would an older address on a "
    "re-issued document, an address written another way, or a misread digit. A finding titled 'Minor mismatch' is a near miss: "
    "the same numbers and text that is close but not identical, such as an abbreviation or a typing slip.",
    ["Compare the marked addresses with each page, number by number.",
     "Ask which address is current and confirm it with the issuer."],
    "The addresses could not be compared here, or a difference was found that could not be trusted because an address was "
    "unreadable or read with low confidence. Whether the addresses agree is unknown."))
TEMPLATES.update(_across(
    "cross_employer",
    "The employer named in two or more documents is not the same by the measure the finding states. Words such as Pvt and Ltd "
    "are put aside. A change of employer would cause this, and so would a trading name or abbreviation in one document and the "
    "registered name in another, or a misread word. A finding titled 'Minor mismatch' is a near miss: names that are close but "
    "not identical, which a typing slip or a misread letter would also give.",
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
    "cross_emi",
    "The existing EMI declared on the application is lower than the instalments that debits on the bank statement name, by more "
    "than the stated tolerance. A loan left out of the declaration would cause this, and so would a debit that is not an "
    "instalment of the applicant's own (a payment for someone else, or a transfer whose narration only says loan), a loan taken "
    "since the application was written, a declared figure that covers part of the debts, or a misread digit or word. The "
    "comparison reads narrations for the words EMI, instalment and loan, so an instalment paid under a lender's name alone is "
    "not seen.",
    ["Compare the declared EMI and the marked debits with each page, digit by digit and word by word.",
     "Ask the applicant which loans the declared figure covers, and the lender for the repayment record."],
    "The declared existing EMI could not be compared with the instalments here, because the figure, an amount, a date or a "
    "narration was unreadable, or a page was too poor to use. Whether they agree is unknown."))
TEMPLATES.update(_across(
    "cross_dates",
    "One or more documents are dated after the application they were submitted with. A wrongly entered or changed date would "
    "cause this, and so would an application filled in earlier than it was submitted, a document re-issued afterwards, a date "
    "written in a different convention (dates are read day first, DD/MM/YYYY), or a misread digit.",
    ["Compare the marked dates with each page.",
     "Ask the applicant and the lender when each document was received."],
    "The dates could not be compared here, or a difference was found that could not be trusted because a date was unreadable, "
    "ambiguous or read with low confidence. Whether the documents are dated in order is unknown."))
TEMPLATES.update(_across(
    "signature",
    "The signature on one document is not the same shape as the signature on another, by the measure the finding states. A "
    "different hand would cause this, and so would one person signing in a different way on different occasions, a pen of another "
    "kind, a scan or photograph that distorts the strokes, or marks that lie over the signature. The comparison reads shapes only: "
    "it does not say who signed, and a signature copied from another document would pass it.",
    ["Open each signature and compare the two by eye, at full size.",
     "Ask the signatory, or whoever issued the document that differs, to confirm who signed it."],
    "The signatures could not be compared in full here, because a caption was not found, no ink lay above it, a page was too poor "
    "or too much turned to straighten, or the area held printed matter. Whether the signatures agree is unknown."))
TEMPLATES.update(_across(
    "mark",
    "The logo or the stamp on one document is not the same shape as the one on another document of the same issuer, by the measure the "
    "finding states. A mark of another issuer would cause this, and so would a form re-issued with a changed mark, a stamp pressed "
    "askew or only in part, a scan or photograph that blurs a fine mark, or printed matter that lies over it. The comparison reads "
    "shapes only: it does not say who issued the document, and a mark copied from another document would pass it.",
    ["Open each mark and compare the two by eye, at full size.",
     "Ask the issuer to confirm that it issued the document that differs, and in which form."],
    "The marks could not be compared in full here, because a page was too poor or too much turned to straighten, the line that names "
    "the issuer or the caption of a stamp was not found, no ink lay where the mark should be, or the area held printed matter. "
    "Whether the marks agree is unknown."))
TEMPLATES.update({
    ("reuse", "observation"): (
        "A signature on one document is the same image as the one on another document, by the measures the finding states. "
        "A hand signs afresh each time, so two separate signings come out close but not the same. "
        "There are ordinary causes all the same: software that places one stored image of a signature on every document it "
        "makes, one page submitted in two forms, or one scan used for two documents. The comparison reads shapes only: it does not say "
        "who signed, or how the image came to be on both documents.",
        ["Open the two signatures and compare them at full size.",
         "Ask the signatory how the signature is put on a document: by hand, or by software from a stored image."]),
})
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
