"""Checks that compare a document with itself (design 7.4). For a bank statement: the balance chain, then the dates. For a
payslip: the totals against the lines and each other, the amount in words, the pay date against the pay month. For a loan
application: the weekday printed with the date against the date.

The statement's chain runs from the opening balance through the balance of every row to the closing balance. Between two balances that
can be read, the later one must equal the earlier one plus the credits and less the debits that lie between them. One changed
balance breaks the two stretches that meet at it, by opposite amounts, so that pair is reported once, at that balance.
The tolerance is the absolute amount_abs only: the relative one is for comparing two documents, and 0.5 % of a large balance
would hide the very edits this check is for. Finding text holds only numbers, dates and row numbers, never the document's words."""
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..config import Thresholds
from ..findings import add_findings, doc_evidence, limitation
from ..model import Case, Document, Evidence, Field, Finding
from ..pipeline import Ctx, guarded
from ..understand.normalise import amount_in_words, parse_amount, parse_month, weekday_of
from . import inconsistency, maybe_demote

BALANCE, DATES, GENERAL = "statement_balance", "statement_dates", "statement_checks"
SLIP_SUMS, SLIP_WORDS, SLIP_DATES, SLIP_GENERAL = "payslip_sums", "payslip_words", "payslip_dates", "payslip_checks"
APP_DATES, APP_GENERAL = "application_dates", "application_checks"
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SHOWN = 6  # rows listed in a sentence before "and N more"


@dataclass
class _Row:
    n: int
    date: Field | None
    debit: Field | None
    credit: Field | None
    balance: Field | None


def _inr(x: Decimal) -> str:
    return f"INR {x:.2f}"


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _amount(f: Field | None) -> Decimal | None:
    return None if f is None or f.value is None else parse_amount(f.value)


def _day(f: Field | None) -> date | None:
    try:
        return None if f is None or f.value is None else date.fromisoformat(f.value)
    except ValueError:
        return None


def _flow(f: Field | None) -> Decimal | None:
    """A debit or credit cell. Found empty means nothing moved; missing or unreadable is None."""
    if f is not None and f.value is None and not f.word_ids and f.conf > 0:
        return Decimal(0)
    return _amount(f)


def _move(r: _Row) -> Decimal | None:
    debit, credit = _flow(r.debit), _flow(r.credit)
    return None if debit is None or credit is None else credit - debit


def _rows_text(ns: list[int], noun: str = "row") -> str:
    shown = ", ".join(map(str, ns[:SHOWN])) + (f" and {len(ns) - SHOWN} more" if len(ns) > SHOWN else "")
    return f"{noun} {shown}" if len(ns) == 1 else f"{noun}s {shown}"


def _flood(bad: int, total: int) -> bool:
    """Three or more failures, and more than half of all: that is not an edit but a layout read wrongly."""
    return bad >= 3 and 2 * bad > total


def _cells(doc: Document) -> dict[int, dict[str, Field]]:
    """Table cells by row number, then by column name (the part of the field name after its table prefix)."""
    out: dict[int, dict[str, Field]] = {}
    for f in doc.fields:
        if f.row is not None:
            out.setdefault(f.row, {})[f.name.partition(".")[2]] = f
    return dict(sorted(out.items()))


def _rows(doc: Document) -> list[_Row]:
    return [_Row(n, c.get("date"), c.get("debit"), c.get("credit"), c.get("balance")) for n, c in _cells(doc).items()]


# --- the balance chain

def _label(k: int, rows: list[_Row]) -> str:
    """Point k of the chain: 0 is the opening balance, 1..n the balance after each row, n + 1 the closing balance."""
    if k == 0:
        return "the opening balance"
    return "the closing balance" if k > len(rows) else f"the balance in row {rows[k - 1].n}"


def _cite(cells: list[Field | None], rows: list[_Row], a: int, b: int, c: int | None = None) -> list[tuple[Field, str]]:
    """The balances at the ends of a stretch, the one in question first, and every amount that moved inside it."""
    cited = [(cells[b], "balance in question"), (cells[a], "balance before")]
    if c is not None:
        cited.append((cells[c], "balance after"))
    for r in rows[a:b if c is None else c]:  # the rows a + 1 .. b (or c)
        cited += [(f, f"{what} in row {r.n}") for what, f in (("debit", r.debit), ("credit", r.credit))
                  if f is not None and f.value is not None]
    return cited


def _balance_findings(doc: Document, header: dict[str, Field], rows: list[_Row], th: Thresholds) -> list[Finding]:
    tol = Decimal(str(th.amount_abs))
    cells = [header.get("opening_balance"), *(r.balance for r in rows), header.get("closing_balance")]
    bal = [_amount(c) for c in cells]
    moves = [None, *map(_move, rows), Decimal(0)]  # moves[k]: what moved to get from point k - 1 to point k
    known = [k for k, b in enumerate(bal) if b is not None]
    stretches = []  # (earlier point, later point, residual); one with an unreadable amount inside is left out
    for a, b in zip(known, known[1:]):
        if None not in moves[a + 1:b + 1]:
            stretches.append((a, b, bal[b] - bal[a] - sum(moves[a + 1:b + 1])))
    bad = [s for s in stretches if abs(s[2]) > tol]
    if _flood(len(bad), len(stretches)):
        return [limitation(BALANCE, "Balance column does not follow the transactions",
                           f"{len(bad)} of {len(stretches)} balance steps do not add up, which is more than a few edited cells. "
                           "The statement probably uses a layout these checks do not assume (for example the newest "
                           "transaction first, or one signed amount column), so no single row is reported. "
                           f"Tolerance: {_inr(tol)}.", [doc_evidence(doc.id, "balance column")])]
    out, i = [], 0
    while i < len(bad):
        a, b, r = bad[i]
        nxt = bad[i + 1] if i + 1 < len(bad) else None
        if nxt and nxt[0] == b and abs(r + nxt[2]) <= tol:  # the stretch into b and the one out of it, equal and opposite
            c = nxt[1]
            expected = bal[a] + sum(moves[a + 1:b + 1])
            detail = (f"{_cap(_label(b, rows))} is {_inr(bal[b])}. {_cap(_label(a, rows))} ({_inr(bal[a])}) and "
                      f"{_label(c, rows)} ({_inr(bal[c])}) both give {_inr(expected)} once the movements between them "
                      f"are applied, a difference of {_inr(bal[b] - expected)}. Tolerance: {_inr(tol)}.")
            out.append(inconsistency(BALANCE, "arithmetic", f"{_cap(_label(b, rows))} does not follow from the transactions",
                                     detail, _cite(cells, rows, a, b, c)))
            i += 2
            continue
        inside = rows[a:b]
        credits = sum((_flow(x.credit) for x in inside), Decimal(0))
        debits = sum((_flow(x.debit) for x in inside), Decimal(0))
        expected = bal[a] + credits - debits
        via = (f"{_label(a, rows)} ({_inr(bal[a])}) with credits of {_inr(credits)} and debits of {_inr(debits)} "
               f"gives {_inr(expected)}" if inside else f"{_label(a, rows)} is {_inr(bal[a])}")
        detail = (f"{_cap(_label(b, rows))} is {_inr(bal[b])}, but {via} (difference {_inr(bal[b] - expected)}). "
                  f"Tolerance: {_inr(tol)}. A transaction row that could not be read would break the chain here as well.")
        out.append(inconsistency(BALANCE, "arithmetic", f"{_cap(_label(b, rows))} does not follow from the transactions",
                                 detail, _cite(cells, rows, a, b)))
        i += 1
    return out


# --- the dates

def _in_order(seq: list[int]) -> set[int]:
    """The positions of one longest non-decreasing run in seq (patience sorting)."""
    tails: list[int] = []
    ends: list[int] = []
    prev: list[int | None] = []
    for i, x in enumerate(seq):
        k = bisect_right(tails, x)
        if k == len(tails):
            tails.append(x)
            ends.append(i)
        else:
            tails[k], ends[k] = x, i
        prev.append(ends[k - 1] if k else None)
    keep, i = set(), ends[-1] if ends else None
    while i is not None:
        keep.add(i)
        i = prev[i]
    return keep


def _date_findings(doc: Document, header: dict[str, Field], rows: list[_Row]) -> list[Finding]:
    ps, pe = header.get("period_start"), header.get("period_end")
    start, end = _day(ps), _day(pe)
    dated = [(r, d) for r in rows if (d := _day(r.date))]
    out: list[Finding] = []
    flagged: set[int] = set()
    if start and end and start > end:
        out.append(inconsistency(DATES, "arithmetic", "Statement period ends before it starts",
                                 f"The period is shown as {start:%d/%m/%Y} to {end:%d/%m/%Y}.", [(pe, "period end"), (ps, "period start")]))
    elif start and end:
        for word, edge, bound, field, off in (("before", "start", start, ps, [x for x in dated if x[1] < start]),
                                              ("after", "end", end, pe, [x for x in dated if x[1] > end])):
            if not off:
                continue
            flagged |= {r.n for r, _ in off}
            listed = "; ".join(f"row {r.n} on {d:%d/%m/%Y}" for r, d in off[:SHOWN])
            more = f"; and {len(off) - SHOWN} more" if len(off) > SHOWN else ""
            out.append(inconsistency(DATES, "arithmetic", f"Transactions dated {word} the statement period",
                                     f"Dated {word} the period {edge} ({bound:%d/%m/%Y}): {listed}{more}.",
                                     [(r.date, f"date in row {r.n}") for r, _ in off] + [(field, f"period {edge}")]))
    seq = [x for x in dated if x[0].n not in flagged]  # a row already outside the period is not also out of order
    keep = _in_order([d.toordinal() for _, d in seq])
    off = [i for i in range(len(seq)) if i not in keep]
    if _flood(len(off), len(seq)):
        out.append(limitation(DATES, "Transaction dates are not in order throughout",
                              f"{len(off)} of {len(seq)} transaction dates are out of order, which is more than a few edited "
                              "cells. The statement is probably not listed oldest first, so no single row is reported.",
                              [doc_evidence(doc.id, "date column")]))
        return out
    for i in off:
        r, d = seq[i]
        near = [seq[j] for j in (max((j for j in keep if j < i), default=None), min((j for j in keep if j > i), default=None))
                if j is not None]
        around = " and ".join(f"row {q.n} ({e:%d/%m/%Y})" for q, e in near)
        out.append(inconsistency(DATES, "arithmetic", f"Row {r.n} is out of date order",
                                 f"Row {r.n} is dated {d:%d/%m/%Y}. The nearest rows in date order are {around}.",
                                 [(r.date, "date out of order")] + [(q.date, f"date in row {q.n}") for q, _ in near]))
    return out


# --- a statement as a whole

def _gaps(header: dict[str, Field], rows: list[_Row]) -> list[str]:
    """What the checks needed and could not read."""
    out = [n.replace("_", " ") for n in ("opening_balance", "closing_balance") if _amount(header.get(n)) is None]
    out += [n.replace("_", " ") for n in ("period_start", "period_end") if _day(header.get(n)) is None]
    for what, ns in (("date", [r.n for r in rows if _day(r.date) is None]),
                     ("balance", [r.n for r in rows if _amount(r.balance) is None]),
                     ("debit or credit", [r.n for r in rows if _move(r) is None])):
        if ns:
            out.append(f"{what} in all {len(ns)} rows" if len(ns) == len(rows) > 1 else f"{what} in {_rows_text(ns)}")
    return out


def check_statement(doc: Document, th: Thresholds) -> list[Finding]:
    header = {f.name: f for f in doc.fields if f.row is None}
    rows = _rows(doc)
    if not rows:
        return [limitation(GENERAL, "Cannot verify the transactions: no table found",
                           "No transaction table was read from this statement, so its balances and dates could not be checked.",
                           [doc_evidence(doc.id, "no transaction table")])]
    out = _balance_findings(doc, header, rows, th) + _date_findings(doc, header, rows)
    if gaps := _gaps(header, rows):
        out.append(limitation(GENERAL, "Cannot fully verify this statement",
                              "These values are missing or unreadable, so what depends on them could not be checked: "
                              + "; ".join(gaps) + ".", [doc_evidence(doc.id, "values the checks needed")]))
    return out


# --- a payslip

def _net_finding(h: dict[str, Field], tol: Decimal) -> list[Finding]:
    gross, ded, net = (_amount(h.get(k)) for k in ("gross_earnings", "total_deductions", "net_pay"))
    if None in (gross, ded, net) or abs(net - (gross - ded)) <= tol:
        return []
    detail = (f"Net pay is {_inr(net)}. Gross earnings of {_inr(gross)} less total deductions of {_inr(ded)} give "
              f"{_inr(gross - ded)}, a difference of {_inr(net - (gross - ded))}. Tolerance: {_inr(tol)}.")
    return [inconsistency(SLIP_SUMS, "arithmetic", "Net pay does not equal gross earnings less total deductions", detail,
                          [(h["net_pay"], "net pay in question"), (h["gross_earnings"], "gross earnings"),
                           (h["total_deductions"], "total deductions")])]


def _listed_findings(h: dict[str, Field], lines: dict[int, dict[str, Field]], tol: Decimal) -> list[Finding]:
    """Each printed total against the lines listed under it. A blank cell counts as zero; an unreadable one leaves that sum unchecked."""
    out = []
    for name, col, noun, title in (("gross_earnings", "earning_amount", "earning", "Gross earnings do not equal the earnings listed"),
                                   ("total_deductions", "deduction_amount", "deduction",
                                    "Total deductions do not equal the deductions listed")):
        total, cells = _amount(h.get(name)), {n: c[col] for n, c in lines.items() if col in c}
        parts = [_flow(c) for c in cells.values()]
        if total is None or not cells or None in parts:
            continue
        listed = sum(parts, Decimal(0))
        if abs(total - listed) <= tol:
            continue
        label = name.replace("_", " ")
        detail = (f"{_cap(label)} are {_inr(total)}. The {noun}s listed in {_rows_text(list(cells), 'line')} add up to "
                  f"{_inr(listed)}, a difference of {_inr(total - listed)}. Tolerance: {_inr(tol)}.")
        out.append(inconsistency(SLIP_SUMS, "arithmetic", title, detail, [(h[name], f"{label} in question")]
                                 + [(c, f"{noun} in line {n}") for n, c in cells.items() if c.value is not None]))
    return out


def _words_finding(h: dict[str, Field], tol: Decimal) -> list[Finding]:
    net, w = _amount(h.get("net_pay")), h.get("net_pay_words")
    spoken = amount_in_words(w.value) if w is not None and w.value else None
    if net is None or spoken is None or abs(net - spoken) <= tol:
        return []
    detail = (f"Net pay is {_inr(net)} in figures. The amount written in words reads as {_inr(spoken)}, a difference of "
              f"{_inr(net - spoken)}. Tolerance: {_inr(tol)}.")
    return [inconsistency(SLIP_WORDS, "arithmetic", "Net pay in words does not match net pay in figures", detail,
                          [(h["net_pay"], "net pay in figures"), (w, "net pay in words")])]


def _pay_date_finding(h: dict[str, Field]) -> list[Finding]:
    """The pay date falls in the pay month or the month after it (a salary is paid for the month just ended)."""
    pm, pd = h.get("pay_month"), h.get("pay_date")
    month, day = (parse_month(pm.value) if pm is not None and pm.value else None), _day(pd)
    if month is None or day is None or 0 <= day.year * 12 + day.month - (month[0] * 12 + month[1]) <= 1:
        return []
    detail = (f"The pay date is {day:%d/%m/%Y} and the pay month is {month[1]:02d}/{month[0]}. A salary is expected to be "
              "paid in its pay month or the month after it.")
    return [inconsistency(SLIP_DATES, "arithmetic", "Pay date is not in the pay month or the month after", detail,
                          [(pd, "pay date"), (pm, "pay month")])]


def _slip_gaps(h: dict[str, Field], lines: dict[int, dict[str, Field]]) -> list[str]:
    """What the checks needed and could not read."""
    out = [label for name, label in (("gross_earnings", "gross earnings"), ("total_deductions", "total deductions"),
                                     ("net_pay", "net pay")) if _amount(h.get(name)) is None]
    w, pm = h.get("net_pay_words"), h.get("pay_month")
    if w is None or not w.value or amount_in_words(w.value) is None:
        out.append("net pay in words")
    if pm is None or not pm.value or parse_month(pm.value) is None:
        out.append("pay month")
    if _day(h.get("pay_date")) is None:
        out.append("pay date")
    if not lines:
        out.append("the earnings and deductions table")
    for col, label in (("earning_amount", "earning amount"), ("deduction_amount", "deduction amount")):
        if bad := [n for n, c in lines.items() if _flow(c.get(col)) is None]:
            out.append(f"{label} in {_rows_text(bad, 'line')}")
    return out


def check_payslip(doc: Document, th: Thresholds) -> list[Finding]:
    h = {f.name: f for f in doc.fields if f.row is None}
    lines, tol = _cells(doc), Decimal(str(th.amount_abs))
    out = _net_finding(h, tol) + _listed_findings(h, lines, tol) + _words_finding(h, tol) + _pay_date_finding(h)
    if gaps := _slip_gaps(h, lines):
        out.append(limitation(SLIP_GENERAL, "Cannot fully verify this payslip",
                              "These values are missing or unreadable, so what depends on them could not be checked: "
                              + "; ".join(gaps) + ".", [doc_evidence(doc.id, "values the checks needed")]))
    return out


# --- a loan application

def check_application(doc: Document, th: Thresholds) -> list[Finding]:
    """The weekday printed with the date against the date. No weekday printed means nothing to compare. A numeric date that
    reads two ways has low confidence, so a mismatch there is shown by maybe_demote as a possible misreading."""
    d = next((f for f in doc.fields if f.name == "application_date" and f.row is None), None)
    day = _day(d)
    if day is None:
        return [limitation(APP_GENERAL, "Cannot fully verify this application",
                           "These values are missing or unreadable, so what depends on them could not be checked: "
                           "application date.", [doc_evidence(doc.id, "values the checks needed")])]
    printed = weekday_of(d.raw)
    if printed is None or printed == day.weekday():
        return []
    detail = (f"The application date is {day:%d/%m/%Y}, which fell on a {DAY_NAMES[day.weekday()]}. The weekday printed "
              f"with it is {DAY_NAMES[printed]}.")
    return [inconsistency(APP_DATES, "arithmetic", "Weekday does not match the application date", detail,
                          [(d, "application date")])]


WITHIN_CHECKS: dict[str, Callable[[Document, Thresholds], list[Finding]]] = {
    "bank_statement": check_statement, "payslip": check_payslip, "loan_application": check_application}


def run_within_checks(case: Case, ctx: Ctx) -> None:
    for doc in case.documents:
        check = WITHIN_CHECKS.get(doc.doc_type)
        if check is None or not doc.fields:  # no check for this type (extraction has said so), or nothing was extracted
            continue
        poor = [p for p in doc.pages if p.quality_class == "poor"]
        if poor:  # rows on a page this unreliable may be missing, and a missing row looks like a break: check nothing
            ctx.audit.append("system", "doc_check_skipped", {"doc": doc.id, "reason": "poor page", "pages": [p.n for p in poor]})
            add_findings(case, ctx, [limitation(
                "checks", f"Unreliable reading: page {p.n}",
                "This page was read at a quality too low to trust its amounts and dates, so the checks that compare values "
                "inside this document were not run on it. A sharper or higher-resolution copy would allow them.",
                [Evidence(doc=doc.id, page=p.n, box=(0.0, 0.0, float(p.width), float(p.height)), note="page read at poor quality")])
                for p in poor])
            continue
        drafts: list[Finding] = []
        if guarded(ctx, case, "checks", lambda doc=doc, check=check: drafts.extend(check(doc, ctx.th)), doc_id=doc.id):
            ctx.audit.append("system", "doc_checked", {"doc": doc.id, "findings": len(drafts)})
            add_findings(case, ctx, [maybe_demote(case, f, ctx.th) for f in drafts])
