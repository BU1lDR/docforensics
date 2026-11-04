"""Layout B, the second layout of the held-out test split. It describes the same things as layout A and is reproducible; and the
wordings meant to be unknown to the spec files are unknown to them, so the test split measures how far the reader reaches beyond
the specs. Adding a synonym for one of them to a spec file after the freeze fails here, on purpose."""
import json

import pytest

from datagen.build import build_split
from datagen.fictional import identity
from datagen.layouts import application, payslip, statement
from datagen.layouts.application import draw_application
from datagen.layouts.payslip import draw_payslip
from datagen.layouts.statement import draw_statement
from datagen.manipulate import METHODS
from docforensics.config import Thresholds
from docforensics.understand.layout import similar
from docforensics.understand.specs import load_specs

TH = Thresholds()
DRAWERS = {"bank_statement": lambda i, lay: draw_statement(i, lay, rows=12, seed=3),
           "payslip": lambda i, lay: draw_payslip(i, lay, seed=3),
           "loan_application": lambda i, lay: draw_application(i, lay, seed=3)}
STYLE = {"bank_statement": statement.STYLE["B"], "payslip": payslip.STYLE["B"], "loan_application": application.STYLE["B"]}

# What layout B prints that a spec file lists (as a label, a column heading or a caption), and what it does not: half and half.
LISTED = {
    "bank_statement": {"Customer Name", "Address", "Statement Period", "Txn Date", "Credit", "Debit", "Balance", "Bank Seal"},
    "payslip": {"Name of Employee", "Salary Month", "Gross Earnings", "Total Deductions", "Net Pay", "Earnings", "Amount Paid",
                "Deductions", "Employee's Signature"},
    "loan_application": {"Date of Application", "Employer Name", "Existing EMI", "Gross Monthly Income", "Tenure in Months",
                         "Signature of Applicant", "For Bank Use"},
}
UNLISTED = {
    "bank_statement": {"A/c Number", "Balance Brought Forward", "Balance Carried Forward", "Narration", "Ref No"},
    "payslip": {"Emp. Code", "Position", "Bank A/c No.", "Paid On", "In Words", "Deducted Amount"},
    "loan_application": {"Full Name", "Present Address", "Salary A/c No", "Amount of Loan"},
}
CAPTIONS = {"bank_statement": ("Bank Seal",), "payslip": (), "loan_application": ("For Bank Use",)}


def printed(kind: str) -> list[str]:
    st = STYLE[kind]
    heads = list(st["heads"].values()) if "heads" in st else []
    return [*st["labels"], *heads, *([st["sign"][2]] if "sign" in st else []), *CAPTIONS[kind]]


@pytest.mark.parametrize("kind", DRAWERS)
def test_b_describes_what_a_describes(kind):
    a, b = (DRAWERS[kind](identity(3), lay) for lay in "AB")
    assert a.truth["layout"] == "A" and b.truth["layout"] == "B" and a.pdf != b.pdf
    for key in ("type", "fields", "rows", "overridden"):
        assert a.truth[key] == b.truth[key], key
    assert set(a.truth["boxes"]) == set(b.truth["boxes"])


@pytest.mark.parametrize("kind", DRAWERS)
def test_b_is_reproducible(kind):
    one, two = (DRAWERS[kind](identity(8), "B") for _ in range(2))
    assert one.pdf == two.pdf and one.truth == two.truth


@pytest.mark.parametrize("kind", DRAWERS)
def test_the_wordings_meant_to_be_unlisted_are_not_in_the_specs(kind):
    spec = load_specs()[kind]
    known = [x.casefold() for f in spec.fields for x in f.labels]
    known += [h.casefold() for c in (spec.table.columns if spec.table else []) for h in c.headers]
    known += [c.casefold() for c in (*spec.signature, *spec.stamp)]
    seen = {text: any(similar(text.casefold(), k, TH.label_sim) for k in known) for text in printed(kind)}
    assert {t for t, hit in seen.items() if hit} == LISTED[kind] & set(seen), kind
    assert {t for t, hit in seen.items() if not hit} == UNLISTED[kind], kind


def test_the_test_split_builds_both_layouts_and_every_method_the_same_way_twice(tmp_path):
    a, b = build_split("test", tmp_path / "a", 36, 0), build_split("test", tmp_path / "b", 36, 0)
    cases = json.loads(a.read_text(encoding="utf-8"))["cases"]
    assert {c["layout"] for c in cases} == {"A", "B"} and {m["method"] for c in cases for m in c["manipulations"]} == set(METHODS)
    assert {(c["layout"], m["method"]) for c in cases for m in c["manipulations"]} >= {(lay, m) for lay in "AB" for m in METHODS}
    for p in sorted((tmp_path / "a").rglob("*.*")):
        assert p.read_bytes() == (tmp_path / "b" / p.relative_to(tmp_path / "a")).read_bytes(), p
