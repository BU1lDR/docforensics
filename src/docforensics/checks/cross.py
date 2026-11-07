"""Checks across documents (design 7.4). What is compared is decided by what a field is (its role) or by the type of the
document, never by what the documents say. A comparison that cannot be made, because a document is missing, a value is
unreadable or a date has no statement to match, is a gap. All the gaps of a run are reported once, together, as one
limitation, so one missing document is not repeated as a limitation per check. Finding text holds only document ids, type
labels, numbers, dates and scores, never the documents' own words: the evidence carries those."""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import combinations

from ..config import Thresholds
from ..findings import add_findings, doc_evidence, field_evidence, limitation
from ..model import Case, Document, Field, Finding
from ..pipeline import Ctx
from ..understand.normalise import _month, name_lacks_a_part, name_similarity, plain, text_similarity
from . import collect, inconsistency, maybe_demote, observation, poor_page, usable
from .within import SHOWN, _amount, _cap, _cells, _day, _flow, _inr, _rows_text

GAPS, PAYER, NET_PAY, INCOME, DATES = "cross_checks", "cross_payer", "cross_net_pay", "cross_income", "cross_dates"
DUPLICATE, PRODUCER, EMI = "cross_duplicate", "cross_producer", "cross_emi"
TYPES = {"bank_statement": "bank statement", "payslip": "payslip", "loan_application": "loan application"}
DATED = {"bank_statement": ("period_end", "period end"), "payslip": ("pay_date", "pay date")}  # the date a document is of
NEEDS = (  # (types on one side, types on the other, what is left uncompared when only one side was submitted)
    (("payslip",), ("bank_statement",), "net pay was not compared with the credits on a bank statement"),
    (("loan_application",), ("payslip",), "declared income was not compared with payslip gross earnings"),
    (("loan_application",), ("bank_statement",), "the declared existing EMI was not compared with the instalment debits on a bank statement"),
    (("loan_application",), ("bank_statement", "payslip"), "the application date was not compared with the dates of the other documents"),
)


def _who(d: Document) -> str:
    return f"{d.id} ({TYPES.get(d.doc_type, 'document')})"


def _docs(docs: list[Document]) -> str:
    return ", ".join(_who(d) for d in docs)


def _of(case: Case, doc_type: str) -> list[Document]:
    return [d for d in case.documents if d.doc_type == doc_type and d.fields]


def _header(doc: Document, name: str) -> Field | None:
    return next((f for f in doc.fields if f.name == name and f.row is None), None)


def gap(text: str, *docs: str) -> Finding:
    """One comparison that could not be made: what is left unchecked and why, and the documents it concerns."""
    return limitation(GAPS, text, "", [doc_evidence(d, "not compared in full") for d in docs])


def fold(gaps: list[Finding], detector: str, title: str, lead: str) -> Finding:
    """All the gaps as one limitation: `lead`, then what each gap says (once), and one whole-document pointer per document."""
    docs = dict.fromkeys(e.doc for g in gaps for e in g.evidence)
    return limitation(detector, title, f"{lead}: {'; '.join(dict.fromkeys(g.title for g in gaps))}.",
                      [doc_evidence(d, "not checked in full") for d in docs])


def _read(case: Case, doc: Document, name: str, label: str, gaps: list[Finding], parse=_amount, min_conf: float = 0.0):
    """(field, parsed value) for a header field that can be used. If it cannot, None, and a gap says which one."""
    f = _header(doc, name)
    x = parse(f) if f is not None and usable(case, f) else None
    why = "could not be read" if x is None else "was read with low confidence" if f.conf < min_conf else ""
    if why:
        gaps.append(gap(f"the {label} in {_who(doc)} {why}", doc.id))
        return None
    return f, x


# --- fields that stand for the same thing in different documents (the extractor gives each its role)

_LEGAL = {"pvt", "ltd", "private", "limited", "inc", "llc", "llp", "co", "corp", "corporation", "company", "plc", "pty", "gmbh"}


def _core(employer: str) -> str:
    """The employer's words without the legal form ('Pvt Ltd', and '(P) Ltd', where (P) stands for Private; a bare P is a word);
    the whole name if nothing else is left."""
    words = re.findall(r"[a-z0-9]+", re.sub(r"\(\s*p\s*\)", " pvt ", employer.casefold()))
    return " ".join([w for w in words if w not in _LEGAL] or words)


SAME, FORM, MINOR, MAJOR = "same", "form", "minor", "major"  # how two writings of one value compare, from alike to far apart


def _grade(identical: bool, form_only: bool, near: bool) -> str:
    return SAME if identical else FORM if form_only else MINOR if near else MAJOR


def _same_name(a: str, b: str, th: Thresholds) -> tuple[str, str]:
    s = name_similarity(a, b)  # 1.0 only when the words are the same once order, titles and initials are put aside
    part = name_lacks_a_part(a, b)  # a middle name left out is a small difference, whatever the similarity says
    return (_grade(plain(a) == plain(b) != "", s == 1.0, s >= th.name_sim or part),
            f"similarity {s:.2f}" + (", one of them has a part the other lacks" if part else ""))


def _parts(address: str) -> list[str]:
    """The comma-separated parts of an address, each in plain form, in a fixed order."""
    return sorted(p for p in map(plain, re.split(r"[,;\n|]", address)) if p)


def _same_address(a: str, b: str, th: Thresholds) -> tuple[str, str]:
    s, nums = text_similarity(a, b), re.findall(r"\d+", a) == re.findall(r"\d+", b)  # a changed flat number is a small change in text
    return (_grade(plain(a) == plain(b) != "", _parts(a) == _parts(b) != [], nums and s >= th.text_sim),
            f"text similarity {s:.2f}" + ("" if nums else ", the numbers in them differ"))


def _same_employer(a: str, b: str, th: Thresholds) -> tuple[str, str]:
    s = text_similarity(_core(a), _core(b))
    return _grade(plain(a) == plain(b) != "", _core(a) == _core(b) != "", s >= th.text_sim), f"text similarity {s:.2f}"


def _tail(short: str, full: str) -> bool:
    t = short.lstrip("X")  # the visible end of a masked number
    return len(t) >= 3 and full.endswith(t)


def _same_account(a: str, b: str, th: Thresholds) -> tuple[str, str]:  # a number has no near miss: it matches or it does not
    x, y = (re.sub(r"[^A-Z0-9]", "", s.upper()) for s in (a, b))
    return SAME if x == y or _tail(x, y) or _tail(y, x) else MAJOR, "the numbers do not match"


ROLES = {  # role: (label, detector, grade(a, b, th) -> (SAME | FORM | MINOR | MAJOR, how alike), the limit as it is printed in the finding)
    "name": ("Name", "cross_name", _same_name,
             lambda th: "Case, spacing and punctuation are ignored; the same words in another order, with other titles or with "
                        f"initials are reported as written differently. Names with a similarity of {th.name_sim:g} or more that are "
                        "still not identical are a minor mismatch, and so is a name that is the other with a whole word left out (a "
                        "middle name) when two words or more are left; names further apart are a mismatch."),
    "address": ("Address", "cross_address", _same_address,
                lambda th: "Case, spacing and punctuation are ignored; the same comma-separated parts in another order are reported "
                           f"as written differently. A text similarity of {th.text_sim:g} or more with the same numbers is a minor "
                           "mismatch; a lower similarity, or other numbers, is a mismatch."),
    "employer": ("Employer", "cross_employer", _same_employer,
                 lambda th: "Case, spacing and punctuation are ignored, and words such as Pvt and Ltd ('(P)' is read as Pvt) are put aside and reported as "
                            f"written differently. A text similarity of {th.text_sim:g} or more between the rest is a minor "
                            "mismatch; a lower one is a mismatch."),
    "account": ("Account number", "cross_account", _same_account,
                lambda th: "Account numbers count as the same when they are equal, or when the visible end (at least 3 characters) of "
                           "a masked or short number is the end of the other; any other difference is a mismatch."),
}
SCAN_CAVEAT = (" One of the values was read from a scan, and a single letter can be a misreading by the OCR: check the picture before "
               "taking this for a different spelling.")


def check_roles(case: Case, th: Thresholds) -> list[Finding]:
    """Per role, every readable pair of documents, graded (design 7.4): a pair that differs in form only makes an observation, a
    near miss a "Minor mismatch" and anything further apart a "Mismatch". Per role and grade one finding lists the pairs and cites
    the fields in them, the one that differs from most of the others first."""
    out: list[Finding] = []
    scans = {(d.id, p.n) for d in case.documents for p in d.pages if p.read_mode == "ocr"}
    for role, (label, detector, grade, limit) in ROLES.items():
        have = [(d, f) for d in case.documents for f in [next((f for f in d.fields if f.role == role and f.row is None), None)] if f]
        if len(have) < 2:  # nothing to compare it with
            continue
        ok = []
        for d, f in have:
            if usable(case, f):
                ok.append((d, f))
            else:
                out.append(gap(f"the {label.lower()} in {_who(d)} could not be read", d.id))
        found: dict[str, list[tuple[int, int, str]]] = {MAJOR: [], MINOR: [], FORM: []}
        for i, j in combinations(range(len(ok)), 2):
            g, how = grade(ok[i][1].value, ok[j][1].value, th)
            if g != SAME:
                found[g].append((i, j, how))
        noun = label.lower()
        for g, bad in found.items():
            if not bad:
                continue
            hits = Counter(k for i, j, _ in bad for k in (i, j))
            order = sorted(hits, key=lambda k: (-hits[k], k))
            listed = "; ".join(f"{_who(ok[i][0])} and {_who(ok[j][0])}" + ("" if g == FORM else f": {how}") for i, j, how in bad[:SHOWN])
            if len(bad) > SHOWN:
                listed += f"; and {len(bad) - SHOWN} more"
            cited = [(ok[k][1], f"{noun} in {_who(ok[k][0])}") for k in order]
            if g == FORM:
                out.append(observation(detector, "cross_document", f"{label} is written differently in the documents",
                                       f"The {noun} has the same words, written differently, in {listed}. {limit(th)}",
                                       [field_evidence(f, note) for f, note in cited], conf=min(f.conf for f, _ in cited)))
                continue
            detail = f"The {noun} differs{' slightly' if g == MINOR else ''} between {listed}. {limit(th)}"
            if g == MINOR and any((f.doc, f.page) in scans for f, _ in cited):
                detail += SCAN_CAVEAT
            out.append(inconsistency(detector, "cross_document", f"{'Minor mismatch' if g == MINOR else 'Mismatch'}: {noun} differs between documents",
                                     detail, cited))
    return out


# --- the employer against whoever paid the salary

_GENERIC = {"neft", "imps", "rtgs", "upi", "ach", "ecs", "salary", "sal", "payroll", "credit", "cr", "transfer", "from", "for", "by",
            "to", "ref", "utr", "inr"}
_NOT_A_NAME = {"the", "messrs", "m", "s"}


def _payer_words(description: str) -> list[str]:
    """What is left of a credit description once transfer terms, month names and short words are dropped."""
    return [w for w in re.findall(r"[a-z]+", description.lower()) if len(w) > 2 and w not in _GENERIC and not _month(w)]


def check_payer(case: Case, th: Thresholds) -> list[Finding]:
    """The first word of an employer, against the payer words of the statement's salary or payroll credits. Heuristic: a trading
    name or an abbreviation that shares no word with the payer is flagged, which the limitations say."""
    stmts = _of(case, "bank_statement")
    out: list[Finding] = []
    for d in case.documents if stmts else ():
        emp = next((f for f in d.fields if f.role == "employer" and f.row is None), None)
        if emp is None:
            continue
        first = next((w for w in re.findall(r"[a-z]+", _core(emp.value)) if w not in _NOT_A_NAME), None) if usable(case, emp) else None
        if first is None:
            out.append(gap(f"the employer in {_who(d)} could not be read", d.id))
            continue
        for st in stmts:
            rows = []
            for cell in _cells(st).values():
                f = cell.get("description")
                if f is not None and usable(case, f) and re.search(r"salary|payroll", f.value.lower()) and (words := _payer_words(f.value)):
                    rows.append((f, words))
            if not rows:
                out.append(gap(f"no salary credit in {_who(st)} names a payer, so the employer in {_who(d)} was not compared with one", d.id, st.id))
                continue
            best = max(text_similarity(first, w) for _, words in rows for w in words)
            if best >= th.text_sim:
                continue
            detail = (f"The employer in {_who(d)} shares no word with the payer in the {len(rows)} salary or payroll credit "
                      f"description{'s' if len(rows) != 1 else ''} of {_who(st)}; the closest word scores {best:.2f}. The payer is "
                      "the words of a description left once transfer terms, month names and words of two letters or fewer are dropped. "
                      f"Words count as the same at a text similarity of {th.text_sim:g} or more.")
            out.append(inconsistency(PAYER, "cross_document", "Employer is not the payer of the salary credits", detail,
                                     [(emp, f"employer in {_who(d)}"), *[(f, f"credit description, row {f.row}") for f, _ in rows[:SHOWN]]]))
    return out


# --- amounts and dates between document types

def check_net_pay(case: Case, th: Thresholds) -> list[Finding]:
    """Each payslip's net pay against the credits of the statements whose period holds its pay date. Every positive credit is a
    candidate, with the tolerance of amount_abs or amount_rel of the larger amount. A pay date outside every period read is a
    gap, not a conflict: a statement for another month looks exactly like it."""
    slips, stmts = _of(case, "payslip"), _of(case, "bank_statement")
    out: list[Finding] = []  # findings and gaps together
    if not slips or not stmts:  # check_inputs says which is missing
        return out
    periods = []
    for st in stmts:
        start, end = (_read(case, st, n, "statement period", out, _day) for n in ("period_start", "period_end"))
        if start and end:
            periods.append((st, start[1], end[1]))
    floor, rel = Decimal(str(th.amount_abs)), Decimal(str(th.amount_rel))
    for slip in slips:
        net, paid = _read(case, slip, "net_pay", "net pay", out), _read(case, slip, "pay_date", "pay date", out, _day)
        if not (net and paid):
            continue
        cover = [st for st, a, b in periods if a <= paid[1] <= b]
        if not cover:
            out.append(gap(f"the pay date in {_who(slip)} is outside the period of every bank statement that could be read, so its "
                           "net pay was not compared with a credit", slip.id, *(st.id for st in stmts)))
            continue
        credits, unread = [], 0
        for st in cover:
            for cell in _cells(st).values():
                f = cell.get("credit")
                x = None if f is None or poor_page(case, f) else _flow(f)
                if x is None:
                    unread += 1
                elif x > 0:
                    credits.append((x, f, cell.get("description")))
        want = net[1]

        def tol(x: Decimal) -> Decimal:
            return max(floor, rel * max(x, want))

        if any(abs(x - want) <= tol(x) for x, _, _ in credits):
            continue
        if unread or not credits:
            what = f"{unread} credit cell{'s' if unread != 1 else ''} in {_docs(cover)} could not be read" if unread \
                else f"no credit was found in {_docs(cover)} for the pay date"
            out.append(gap(f"{what}, so the net pay in {_who(slip)} was not matched to a credit", slip.id, *(st.id for st in cover)))
            continue
        salary = [c for c in credits if c[2] is not None and c[2].value and re.search(r"salary|payroll", c[2].value.lower())]
        x, f, _ = min(salary or credits, key=lambda c: abs(c[0] - want))
        detail = (f"The net pay in {_who(slip)} is {_inr(want)}. No credit in {_docs(cover)} is within the tolerance of it; the nearest "
                  f"is {_inr(x)} in row {f.row}, a difference of {_inr(abs(x - want))}. Tolerance: {_inr(tol(x))} "
                  f"({th.amount_rel:.1%} of the larger amount, at least {_inr(floor)}).")
        out.append(inconsistency(NET_PAY, "cross_document", "Net pay does not match a credit on the bank statement", detail,
                                 [(net[0], "net pay"), (f, f"nearest credit, row {f.row}")]))
    return out


def check_income(case: Case, th: Thresholds) -> list[Finding]:
    """Declared monthly income on an application against the gross earnings of each payslip, within income_rel."""
    apps, slips = _of(case, "loan_application"), _of(case, "payslip")
    out: list[Finding] = []
    if not apps or not slips:
        return out
    limit = Decimal(str(th.income_rel))
    for app in apps:
        income = _read(case, app, "declared_monthly_income", "declared monthly income", out)
        for slip in slips:
            gross = _read(case, slip, "gross_earnings", "gross earnings", out)
            if not (income and gross):
                continue
            if gross[1] <= 0:
                out.append(gap(f"the gross earnings in {_who(slip)} are not a positive amount", slip.id))
                continue
            diff = abs(income[1] - gross[1]) / gross[1]
            if diff <= limit:
                continue
            detail = (f"The declared monthly income in {_who(app)} is {_inr(income[1])} and the gross earnings in {_who(slip)} are "
                      f"{_inr(gross[1])}, a difference of {diff:.1%}. Tolerance: {th.income_rel:.0%} of the gross earnings.")
            out.append(inconsistency(INCOME, "cross_document", "Declared income differs from the payslip gross earnings", detail,
                                     [(income[0], "declared monthly income"), (gross[0], "gross earnings")]))
    return out


_INSTALMENT = re.compile(r"(?<![a-z])(?:emis?|instal+ments?|instl|loans?)(?![a-z])")
_NOT_PAID = re.compile(r"(?<![a-z])(?:fees?|charges?|penalty|penal|gst|tax|reversal|reversed|refund|bounce|bounced|returns?|returned|"
                       r"waiver|insurance|premium|closure|foreclosure|prepayment)(?![a-z])")


def is_instalment(narration: str) -> bool:
    """A narration that names a loan instalment: the whole word EMI, instalment or loan, and no word that makes it a fee, a
    reversal or a closing payment. Whole words only: 'Emirates', 'remittance' and 'seminar' contain the letters emi."""
    t = narration.lower()
    return bool(_INSTALMENT.search(t)) and not _NOT_PAID.search(t)


def _instalments(case: Case, st: Document):
    """What one bank statement shows being paid as instalments: {(year, month): [(amount, debit cell, narration cell, row)]}; the
    rows that name an instalment whose amount or date could not be read, as (row, month or None); the rows of a debit whose
    narration could not be read at all, which nobody can tell from an instalment; and whether a page of poor quality held rows
    that were not used. A credit is not a payment, a narration found empty names nothing, and a poor page is not trusted."""
    paid: dict[tuple[int, int], list[tuple[Decimal, Field, Field, int]]] = {}
    unread: list[tuple[int, tuple[int, int] | None]] = []
    blind: list[int] = []
    poor = False
    for n, cell in _cells(st).items():
        text, debit = cell.get("description"), cell.get("debit")
        if text is None or text.value is None:
            moved = None if debit is None else _flow(debit)
            if moved is not None and moved > 0 and not (text is not None and not text.word_ids and text.conf > 0):  # not found empty
                if poor_page(case, debit):
                    poor = True
                else:
                    blind.append(n)
            continue
        if poor_page(case, text):
            poor = True
            continue
        if not is_instalment(text.value):
            continue
        debit = cell.get("debit")
        x = None if debit is None or poor_page(case, debit) else _flow(debit)
        if x == 0:
            continue
        day = _day(cell.get("date"))
        month = (day.year, day.month) if day else None
        if x is None or x < 0 or month is None:
            unread.append((n, month))
        else:
            paid.setdefault(month, []).append((x, debit, text, n))
    return paid, unread, blind, poor


def check_emi(case: Case, th: Thresholds) -> list[Finding]:
    """The existing EMI declared on an application against the instalments each bank statement shows being paid. Debits that
    name an instalment are added up per calendar month, and the month with the most paid is compared with the declared figure,
    one statement at a time. Only a total above the declared figure by more than the tolerance is a finding: a declared figure
    above what the statement shows has ordinary causes (an instalment paid from another account, or in cash), and a statement
    with no instalment debit leaves the declared figure alone. Rows or pages that could not be used are gaps."""
    apps, stmts = _of(case, "loan_application"), _of(case, "bank_statement")
    out: list[Finding] = []
    if not apps or not stmts:
        return out
    floor, rel = Decimal(str(th.amount_abs)), Decimal(str(th.emi_rel))
    seen = {st.id: _instalments(case, st) for st in stmts}
    for app in apps:
        field = _header(app, "existing_emi")
        declared = _amount(field) if field is not None and usable(case, field) else None
        for st in stmts:
            paid, unread, blind, poor = seen[st.id]
            if poor:
                out.append(gap(f"{_who(st)} has rows on a page of poor quality, so any instalment among them was not compared with "
                               f"the existing EMI in {_who(app)}", st.id, app.id))
            if blind:
                out.append(gap(f"the narration could not be read for {_rows_text(blind)} in {_who(st)}, so any instalment among those "
                               f"debits was not compared with the existing EMI in {_who(app)}", st.id, app.id))
            if not paid and not unread:
                continue
            if declared is None:
                out.append(gap(f"the existing EMI in {_who(app)} could not be read, so the instalment debits in {_who(st)} were not "
                               "compared with it", app.id, st.id))
                continue
            if paid:
                month, rows = max(paid.items(), key=lambda kv: sum(r[0] for r in kv[1]))  # the first month if two are level
                total = sum((r[0] for r in rows), Decimal(0))
                tol = max(floor, rel * total)  # the total is the larger amount whenever it is the one in question
                if total - declared > tol:
                    out.append(_emi_finding(app, st, field, declared, month, rows, total, tol, floor,
                                            [n for n, m in unread if m in (None, month)], th))
                    continue
            if unread:
                out.append(gap(f"{_rows_text([n for n, _ in unread])} in {_who(st)} named an instalment but its amount or date could "
                               f"not be read, so the instalments paid were not compared in full with the existing EMI in {_who(app)}",
                               st.id, app.id))
    return out


def _emi_finding(app, st, field, declared, month, rows, total, tol, floor, unread, th) -> Finding:
    unseen = f" {_cap(_rows_text(unread))} could not be read, so the total is a minimum." if unread else ""
    detail = (f"The existing EMI declared in {_who(app)} is {_inr(declared)}. {_who(st)} shows debits that name an instalment "
              f"({_rows_text([r[3] for r in rows])}) totalling {_inr(total)} in {datetime(*month, 1):%B %Y}, {_inr(total - declared)} "
              f"more than declared.{unseen} Tolerance: {_inr(tol)} ({th.emi_rel:.0%} of the instalments paid, at least {_inr(floor)}).")
    cited = [(field, "declared existing EMI")]
    for amount, debit, text, n in rows[:SHOWN]:
        cited += [(debit, f"instalment debit, row {n}"), (text, f"narration, row {n}")]
    return inconsistency(EMI, "cross_document", "Declared existing EMI is lower than the instalments on the bank statement", detail, cited)


def check_application_dates(case: Case, th: Thresholds) -> list[Finding]:
    """Documents submitted with an application cannot be dated after it: a statement's period end, a payslip's pay date."""
    apps = _of(case, "loan_application")
    others = [d for t in DATED for d in _of(case, t)]
    out: list[Finding] = []
    if not apps or not others:
        return out
    for app in apps:
        when = _read(case, app, "application_date", "application date", out, _day)
        late = []
        for d in others:
            name, label = DATED[d.doc_type]
            got = _read(case, d, name, label, out, _day)
            if got and when and got[1] > when[1]:
                late.append((d, label, *got))
        if late:
            listed = "; ".join(f"the {label} in {_who(d)} is {day:%d/%m/%Y}" for d, label, _, day in late)
            out.append(inconsistency(DATES, "cross_document", "Application is dated before documents submitted with it",
                                     f"The application date in {_who(app)} is {when[1]:%d/%m/%Y}, and {listed}. These documents are "
                                     "dated after the application.",
                                     [(when[0], "application date"), *[(f, f"{label} in {_who(d)}") for d, label, f, _ in late]]))
    return out


# --- the files themselves

def check_duplicates(case: Case, th: Thresholds) -> list[Finding]:
    """The same bytes submitted twice."""
    groups: dict[str, list[Document]] = {}
    for d in case.documents:
        groups.setdefault(d.sha256, []).append(d)
    return [observation(DUPLICATE, "metadata", "The same file was submitted more than once",
                        f"{_docs(docs)} are the same file: their SHA-256 digests are equal.",
                        [doc_evidence(d.id, "same file") for d in docs])
            for docs in groups.values() if len(docs) > 1]


_PDF_DATE = re.compile(r"D:(\d{14})(?:([+-])(\d{2})'?(\d{2})'?|Z)?")


def _created(d: Document) -> datetime | None:
    """The creation time from the PDF's metadata, with its offset; no offset is read as UTC. Anything else is None."""
    m = _PDF_DATE.match(d.meta.get("creationDate", ""))
    if not m:
        return None
    try:
        off = timedelta(hours=int(m[3] or 0), minutes=int(m[4] or 0))
        return datetime.strptime(m[1], "%Y%m%d%H%M%S").replace(tzinfo=timezone(-off if m[2] == "-" else off))
    except ValueError:
        return None


def check_producer(case: Case, th: Thresholds) -> list[Finding]:
    """Documents of different kinds made by the same software within same_tool_minutes of each other. Missing or unreadable
    metadata is skipped: most scans carry none."""
    by_tool: dict[str, list[tuple[Document, datetime]]] = {}
    for d in case.documents:
        tool, made = d.meta.get("producer", "").strip(), _created(d)
        if tool and made:
            by_tool.setdefault(tool, []).append((d, made))
    out, limit = [], timedelta(minutes=th.same_tool_minutes)
    for group in by_tool.values():
        close = [(a, b) for a, b in combinations(group, 2) if a[0].doc_type != b[0].doc_type and abs(a[1] - b[1]) <= limit]
        if not close:
            continue
        ids = dict.fromkeys(d.id for pair in close for d, _ in pair)
        docs = [d for d, _ in group if d.id in ids]
        apart = max(abs(a[1] - b[1]) for a, b in close).total_seconds() / 60
        out.append(observation(PRODUCER, "metadata", "Documents of different kinds come from the same software, created minutes apart",
                               f"{_docs(docs)} name the same producing software and were created at most {apart:.0f} minutes apart "
                               f"(limit {th.same_tool_minutes}).", [doc_evidence(d.id, "same producing software") for d in docs]))
    return out


def check_inputs(case: Case, th: Thresholds) -> list[Finding]:
    """What was not submitted, or not understood, and so what could not be compared."""
    out = []
    for d in case.documents:
        if d.doc_type not in TYPES:
            out.append(gap(f"{d.id} was not recognised as a bank statement, payslip or loan application", d.id))
        elif not d.fields:
            out.append(gap(f"no field could be read from {_who(d)}", d.id))
    have = {t for t in TYPES if _of(case, t)}
    for a, b, what in NEEDS:
        in_a, in_b = have & set(a), have & set(b)
        if bool(in_a) != bool(in_b):
            lacking, present = (a, b) if not in_a else (b, a)
            out.append(gap(f"no {' or '.join(TYPES[t] for t in lacking)} was submitted, so {what}",
                           *(d.id for t in present for d in _of(case, t))))
    return out


CROSS_CHECKS = [check_inputs, check_roles, check_payer, check_net_pay, check_income, check_emi, check_application_dates,
                check_duplicates, check_producer]


def run_cross_checks(case: Case, ctx: Ctx) -> None:
    n = len(case.documents)
    if n == 0:
        return
    if n == 1:
        add_findings(case, ctx, [limitation(
            GAPS, "Cannot check across documents: one document submitted",
            "Only one document was submitted, so no comparison with another document could run. The checks inside the document "
            "were still applied.", [doc_evidence(case.documents[0].id, "the only document")])])
        return
    drafts = collect(case, ctx, CROSS_CHECKS)  # the module's list, read now
    gaps = [f for f in drafts if f.detector == GAPS]
    found = [f for f in drafts if f.detector != GAPS]
    if gaps:
        found.append(fold(gaps, GAPS, "Some cross-document comparisons could not be made",
                          "These comparisons could not be made in full, so what depends on them is unchecked"))
    ctx.audit.append("system", "cross_checked", {"documents": n, "findings": len(found)})
    add_findings(case, ctx, [maybe_demote(case, f, ctx.th) for f in found])
