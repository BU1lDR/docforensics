"""Statement checks (design 7.4): the balance chain, the dates, and what a doubtful reading may not claim.
Tampered statements are drawn with one cell changed and nothing recomputed, so the truth says which cell the finding must cite."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from datagen.fictional import identity
from datagen.layouts import money
from datagen.layouts.statement import draw_statement
from docforensics.checks import maybe_demote, run_checks
from docforensics.config import Thresholds
from docforensics.findings import field_evidence
from docforensics.ingest import create_case
from docforensics.model import Case, Document, Evidence, Field, Finding, Page
from docforensics.pipeline import Ctx, run_case
from docforensics.understand.extract import extract_document
from docforensics.understand.specs import load_specs
from tests.helpers import iou, lines_pdf

TH = Thresholds()
SPEC = load_specs()["bank_statement"]
NO_BALANCE = {"head.balance": "Remarks"}  # a heading no column is called: every balance cell reads as missing


def stmt(seed=1, rows=12, over=None):
    return draw_statement(identity(seed), rows=rows, seed=seed, overrides=over)


def moved(seed, key, delta, rows=12, extra=None):
    """The statement of this seed with one amount changed by delta and nothing else recomputed: a clumsy edit."""
    col, _, n = key.partition("@")
    truth = stmt(seed, rows).truth
    old = truth["rows"][int(n) - 1][col] if n else truth["fields"][col]
    return stmt(seed, rows, {key: money(Decimal(old) + delta), **(extra or {})})


def run(tmp_path, *pdfs, th=TH, scan=None):
    """The pipeline over these statements. With scan ('degraded' or 'poor') the first one is taken to be an OCR read of that
    quality: its fields are extracted again at that reliability and the checks run again."""
    case, cd, audit = create_case(tmp_path / "data", [(f"s{i}.pdf", p) for i, p in enumerate(pdfs, 1)], th)
    case = run_case(cd, th)
    if scan:
        case.findings.clear()
        doc = case.documents[0]
        for page in doc.pages:
            page.read_mode, page.quality_class = "ocr", scan
        doc.fields = extract_document(doc, SPEC, th)
        run_checks(case, Ctx(cd, audit, th))
    return case


def on(e, drawn, key):
    page, *box = drawn.truth["boxes"][key]
    return e.page == page and iou(e.box, box) >= 0.9


def at(f, drawn, key):
    """The finding's first evidence sits on this drawn cell."""
    return on(f.evidence[0], drawn, key)


def cites(f, drawn, key):
    return any(on(e, drawn, key) for e in f.evidence)


def period_pdf(period):
    """A bare statement: enough keywords to classify, one period line, no table."""
    return lines_pdf([(40, 60, "Halcyon Test Bank", 18), (40, 80, "Statement of Account", 11), (40, 130, "Statement Period", 9),
                      (160, 130, period, 9)])


# --- the balance chain

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_genuine_statement_has_no_findings(tmp_path, seed):
    assert [f.title for f in run(tmp_path, stmt(seed).pdf).findings] == []


def test_changed_balance_flagged_at_its_row(tmp_path):
    drawn = moved(2, "balance@5", Decimal(5000))
    case = run(tmp_path, drawn.pdf)
    (f,) = case.findings  # a changed balance breaks the step into its row and the step out of it: still one finding
    assert (f.fclass, f.detector, f.family, f.status) == ("inconsistency", "statement_balance", "arithmetic", "open")
    assert at(f, drawn, "balance@5") and "row 5" in f.title and f.conf >= TH.low_conf
    cell = next(x for x in case.documents[0].fields if x.id == f.evidence[0].field_id)
    assert (cell.name, cell.row) == ("txn.balance", 5) and f.evidence[0].value == cell.value


def test_balance_chain_across_pages(tmp_path):
    case = run(tmp_path, stmt(3, rows=70).pdf)
    assert len(case.documents[0].pages) == 3 and case.findings == []


@pytest.mark.parametrize("row, page", [(30, 1), (31, 2), (61, 3)])
def test_break_at_a_page_boundary_is_found_once(tmp_path, row, page):
    drawn = moved(3, f"balance@{row}", Decimal(750), rows=70)
    (f,) = run(tmp_path, drawn.pdf).findings
    assert at(f, drawn, f"balance@{row}") and f.evidence[0].page == page


def test_changed_amount_is_flagged_at_its_row(tmp_path):
    drawn = moved(1, "credit@2", Decimal(1000))  # the salary: only the step into row 2 breaks
    (f,) = run(tmp_path, drawn.pdf).findings
    assert "row 2" in f.title and at(f, drawn, "balance@2")
    assert cites(f, drawn, "credit@2") and cites(f, drawn, "balance@1")


def test_changed_last_balance_is_flagged_at_its_row(tmp_path):
    drawn = moved(1, "balance@12", Decimal(900))
    (f,) = run(tmp_path, drawn.pdf).findings
    assert at(f, drawn, "balance@12")


def test_changed_closing_balance_is_flagged_against_the_last_row(tmp_path):
    drawn = moved(1, "closing_balance", Decimal(-2500))
    (f,) = run(tmp_path, drawn.pdf).findings
    assert at(f, drawn, "closing_balance") and cites(f, drawn, "balance@12") and "closing balance" in f.title


def test_detail_prints_tolerance(tmp_path):
    (f,) = run(tmp_path, moved(2, "balance@5", Decimal(5000)).pdf).findings
    assert "Tolerance: INR 1.00" in f.detail and "5000.00" in f.detail  # the size of the gap, in plain digits


def test_tolerance_comes_from_the_config(tmp_path):
    wide = Thresholds(amount_abs=5.0)
    small = moved(2, "balance@5", Decimal(3)).pdf
    assert [f.fclass for f in run(tmp_path / "a", small).findings] == ["inconsistency"]
    assert run(tmp_path / "b", small, th=wide).findings == []
    (f,) = run(tmp_path / "c", moved(2, "balance@5", Decimal(6)).pdf, th=wide).findings
    assert "Tolerance: INR 5.00" in f.detail


def test_missing_balance_column_falls_back_to_the_totals(tmp_path):
    (lim,) = run(tmp_path / "a", stmt(5, over=NO_BALANCE).pdf).findings
    assert lim.fclass == "processing_limitation" and "Cannot fully verify" in lim.title
    assert "balance in all 12 rows" in lim.detail  # said, not skipped
    drawn = moved(5, "credit@2", Decimal(1000), extra=NO_BALANCE)
    found = run(tmp_path / "b", drawn.pdf).findings
    (bad,) = [f for f in found if f.fclass == "inconsistency"]
    assert at(bad, drawn, "closing_balance") and cites(bad, drawn, "opening_balance") and cites(bad, drawn, "credit@2")
    assert [f.fclass for f in found].count("processing_limitation") == 1


def test_statement_without_a_table_says_so(tmp_path):
    case = run(tmp_path, period_pdf("01/05/2026 to 31/05/2026"))
    assert [(f.fclass, f.title) for f in case.findings] == [
        ("processing_limitation", "Cannot verify the transactions: no table found")]


def test_chain_broken_throughout_is_a_layout_problem_not_twelve_findings(tmp_path):
    over = {f"balance@{i}": money(1000 * i) for i in range(2, 11)}  # nine balances unrelated to their neighbours
    (f,) = run(tmp_path, stmt(1, over=over).pdf).findings
    assert f.fclass == "processing_limitation" and "layout" in f.detail


def test_finding_text_never_quotes_the_document(tmp_path):
    hostile = "<b onmouseover=alert(1)>x</b>"
    (f,) = run(tmp_path, moved(2, "balance@5", Decimal(5000), extra={"description@5": hostile}).pdf).findings
    text = " ".join([f.title, f.detail, *(e.note + (e.value or "") for e in f.evidence)])
    assert "<b" not in text and "alert" not in text


# --- the dates

def test_dates_outside_period_and_out_of_order(tmp_path):
    base = stmt(2)
    start, end = (date.fromisoformat(base.truth["fields"][k]) for k in ("period_start", "period_end"))
    assert all(date.fromisoformat(base.truth["rows"][i]["date"]) > start for i in (5, 6))  # row 8 will be the odd one out
    over = {"date@3": f"{end + timedelta(days=3):%d/%m/%Y}", "date@5": f"{start - timedelta(days=2):%d/%m/%Y}",
            "date@8": f"{start:%d/%m/%Y}"}
    drawn = stmt(2, over=over)
    found = run(tmp_path, drawn.pdf).findings
    assert sorted((f.fclass, f.detector) for f in found) == [("inconsistency", "statement_dates")] * 3
    after, before, order = (next(f for f in found if word in f.title) for word in ("after", "before", "order"))
    assert cites(after, drawn, "date@3") and cites(after, drawn, "period_end")
    assert cites(before, drawn, "date@5") and cites(before, drawn, "period_start")
    assert at(order, drawn, "date@8") and "Row 8" in order.title  # a row already outside the period is not also out of order


def test_period_that_ends_before_it_starts(tmp_path):
    drawn = stmt(2, over={"period_end": "01/01/2020"})
    (f,) = run(tmp_path, drawn.pdf).findings  # and no row is then called "after the period"
    assert f.detector == "statement_dates" and "before it starts" in f.title
    assert cites(f, drawn, "period_start") and cites(f, drawn, "period_end")


def test_ambiguous_dates_demote_a_date_conflict(tmp_path):
    base = stmt(2).truth["fields"]
    year, month = base["period_start"][:4], int(base["period_start"][5:7])
    ends = 2 if month != 2 else 3
    days = [d for d in range(4, 13) if d != month]  # every date can be read day-first or month-first
    over = {"period_end": f"{ends:02d}/{month:02d}/{year}"} | {f"date@{i}": f"{days[i % len(days)]:02d}/{month:02d}/{year}"
                                                               for i in range(1, 13)}
    found = [f for f in run(tmp_path, stmt(2, over=over).pdf).findings if f.detector == "statement_dates"]
    assert found and all(f.fclass == "processing_limitation" and f.title.startswith("Possible extraction error, verify:")
                         for f in found)


# --- doubtful readings

def test_degraded_page_failure_is_demoted(tmp_path):
    drawn = moved(2, "balance@5", Decimal(5000))
    (f,) = run(tmp_path / "a", drawn.pdf, scan="degraded").findings
    assert f.fclass == "processing_limitation" and f.title.startswith("Possible extraction error, verify:")
    assert at(f, drawn, "balance@5") and f.family == "limitation"  # still points at the cell, but is no longer called a conflict
    assert run(tmp_path / "b", stmt(2).pdf, scan="degraded").findings == []  # a pass on a doubtful page stays a pass


def test_poor_page_runs_no_field_checks(tmp_path):
    (f,) = run(tmp_path, moved(2, "balance@5", Decimal(5000)).pdf, scan="poor").findings
    assert (f.fclass, f.title) == ("processing_limitation", "Unreliable reading: page 1") and f.evidence[0].page == 1


def test_poor_page_leaves_other_documents_checked(tmp_path):
    poor, other = moved(2, "balance@5", Decimal(5000)), moved(3, "balance@4", Decimal(700))
    case = run(tmp_path, poor.pdf, other.pdf, scan="poor")
    first, second = case.documents
    assert [f.title for f in case.findings if f.evidence[0].doc == first.id] == ["Unreliable reading: page 1"]
    (f,) = [f for f in case.findings if f.evidence[0].doc == second.id]
    assert f.fclass == "inconsistency" and at(f, other, "balance@4")


def finding(fclass="inconsistency", conf=1.0, page=1):
    return Finding(fclass=fclass, detector="t", family="arithmetic", title="T", detail="d", conf=conf,
                   evidence=[Evidence(doc="D1", page=page, box=(0.0, 0.0, 1.0, 1.0))])


def test_maybe_demote_only_touches_doubtful_inconsistencies():
    doc = Document(id="D1", sha256="0", filename="a.pdf", stored_path="a.pdf", pages=[Page(n=1, width=10, height=10)])
    case = Case(id="C", created="2026-11-02T00:00:00+00:00", documents=[doc])
    page = case.documents[0].pages[0]
    assert maybe_demote(case, finding(), TH).fclass == "inconsistency"  # text layer
    assert maybe_demote(case, finding(conf=0.4), TH).fclass == "processing_limitation"  # below LOW_CONF
    page.read_mode, page.quality_class = "ocr", "good"
    assert maybe_demote(case, finding(), TH).fclass == "inconsistency"
    for quality in ("degraded", "poor"):  # a number read by OCR from a doubtful page, whatever its own confidence says
        page.quality_class = quality
        assert maybe_demote(case, finding(), TH).fclass == "processing_limitation"
        assert maybe_demote(case, finding(page=0), TH).fclass == "inconsistency"  # a whole-document pointer reads no page
    for other in ("observation", "potential_manipulation", "processing_limitation"):
        f = finding(other, conf=0.1)
        assert maybe_demote(case, f, TH) == f


def test_field_evidence_carries_the_place_and_the_value():
    f = Field(id="D1-f1", doc="D1", name="x", raw="1,00.00", value="100.00", kind="amount", conf=0.9, page=2,
              box=(1.0, 2.0, 3.0, 4.0))
    assert field_evidence(f, "n") == Evidence(doc="D1", page=2, box=(1.0, 2.0, 3.0, 4.0), note="n", field_id="D1-f1",
                                              value="100.00")
