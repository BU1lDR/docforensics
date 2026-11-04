"""Task 19: the dataset builder (datagen/build.py) and the scorer (evaluation/score.py). The scorer is the only code that reads the
manifest; the product never does."""
import hashlib
import json
import re
from pathlib import Path

import pytest

from datagen.build import SPLIT_SPAN, build_split, plan_cases
from datagen.manipulate import METHODS, TEST_ONLY
from evaluation.run_eval import evaluate
from evaluation.score import format_report, score
from docforensics.model import Case, Document, Evidence, Field, Finding, Page

VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)
SRC = Path(__file__).resolve().parents[1] / "src" / "docforensics"


def doc(i, filename, doc_type="unknown", fields=(), pages=1):
    return Document(id=f"D{i}", sha256="0" * 64, filename=filename, stored_path=f"docs/{filename}", doc_type=doc_type,
                    pages=[Page(n=n, width=1654, height=2339) for n in range(1, pages + 1)], fields=list(fields))


def flag(detector, *places, fclass="inconsistency", family="cross_document", title="a finding"):
    """A finding citing (doc id, page, box) places."""
    return Finding(fclass=fclass, detector=detector, family=family, title=title,
                   evidence=[Evidence(doc=d, page=p, box=b) for d, p, b in places])


def case(name, files, findings=(), pages=1):
    return Case(id=name, created="2026-11-04T00:00:00Z", documents=[doc(i, f, pages=pages) for i, f in enumerate(files, 1)],
                findings=list(findings))


def entry(name, files, medium="digital", layout="A", genuine=False, manipulations=()):
    return {"case": name, "seed": 1, "layout": layout, "medium": medium, "genuine": genuine,
            "docs": [{"file": f, "type": t, "fields": {}, "rows": [], "boxes": {}, "truth_valid": True} for f, t in files],
            "manipulations": list(manipulations)}


def manip(method, file, box=None, variant="", also=()):
    return {"method": method, "variant": variant, "doc": file, "page": 1 if box else 0, "box": box, "field": None, "note": "",
            "also": list(also)}


STATEMENT, SLIP, APP = ("01_statement.pdf", "bank_statement"), ("02_payslip.pdf", "payslip"), ("03_application.pdf", "loan_application")
NONE = (0, 0, 0, 0)
HERE = [100, 100, 200, 150]


def hand_made():
    """Seven cases whose right scores are known by hand."""
    manifest = {"split": "dev", "cases": [
        entry("c1", [STATEMENT, SLIP, APP], manipulations=[manip("D1", "01_statement.pdf", HERE, "a credit")]),
        entry("c2", [STATEMENT, SLIP, APP], manipulations=[manip("D1", "02_payslip.pdf", HERE, "net pay")]),
        entry("c3", [STATEMENT, SLIP, APP], manipulations=[manip("D2", "02_payslip.pdf", HERE, "net pay")]),
        entry("c4", [STATEMENT, SLIP, APP], manipulations=[manip("D4", "03_application.pdf")]),
        entry("c5", [STATEMENT, SLIP, APP, ("04_statement_copy.pdf", "bank_statement")],
              manipulations=[manip("C3", "04_statement_copy.pdf", also=["01_statement.pdf"])]),
        entry("c6", [STATEMENT, SLIP, APP], genuine=True),
        entry("c7", [STATEMENT, SLIP, APP], genuine=True)]}
    cases = {
        "c1": case("c1", [f for f, _ in (STATEMENT, SLIP, APP)], [flag("pdf_revisions", ("D1", 1, tuple(HERE)))]),
        "c2": case("c2", [f for f, _ in (STATEMENT, SLIP, APP)], [flag("cross_net_pay", ("D2", 1, (100, 100, 200, 250)), ("D1", 1, (5, 5, 6, 6)))]),
        "c3": case("c3", [f for f, _ in (STATEMENT, SLIP, APP)],
                   [flag("pdf_overlay", ("D2", 0, NONE), fclass="processing_limitation", family="limitation", title="Hidden text only partly examined")]),
        "c4": case("c4", [f for f, _ in (STATEMENT, SLIP, APP)], [flag("pdf_meta", ("D3", 0, NONE), fclass="observation", family="metadata")]),
        "c5": case("c5", ["01_statement.pdf", "02_payslip.pdf", "03_application.pdf", "04_statement_copy.pdf"],
                   [flag("cross_duplicate", ("D1", 0, NONE), ("D4", 0, NONE))]),
        "c6": case("c6", [f for f, _ in (STATEMENT, SLIP, APP)],
                   [flag("cross_name", ("D1", 1, (1, 1, 2, 2)), ("D2", 1, (1, 1, 2, 2)), title="Minor mismatch: name differs between documents"),
                    flag("mark", ("D1", 0, NONE), fclass="processing_limitation", family="limitation", title="Issuer marks only partly compared")]),
        "c7": case("c7", [f for f, _ in (STATEMENT, SLIP, APP)])}
    return manifest, cases


def test_score_counts_hits_and_misses():
    res = score(*hand_made(), timings={})
    d1 = res["methods"]["D1"]
    assert (d1["n"], d1["found"], d1["located"]) == (2, 2, 1)  # IoU 1 and 1/3: flagged near the place both times, located once
    assert d1["mean_iou"] == pytest.approx(2 / 3)
    assert (res["methods"]["D2"]["n"], res["methods"]["D2"]["found"]) == (1, 0)  # a limitation is not a find
    assert (res["methods"]["D4"]["n"], res["methods"]["D4"]["found"], res["methods"]["D4"]["located"]) == (1, 1, None)
    assert (res["methods"]["C3"]["n"], res["methods"]["C3"]["found"]) == (1, 1)  # citing the other copy counts
    (miss,) = res["misses"]
    assert (miss["case"], miss["method"]) == ("c3", "D2") and "limitation" in miss["why"]
    g = res["genuine"]
    assert (g["cases"], g["documents"], g["flags"], g["cases_with_flags"], g["limitations"]) == (2, 6, 1, 1, 1)
    assert g["per_document"] == pytest.approx(1 / 6)
    assert [(f["case"], f["detector"]) for f in g["list"]] == [("c6", "cross_name")] and g["by_detector"] == {"cross_name": 1}
    assert res["counts"]["cases"] == 7 and res["counts"]["genuine_cases"] == 2 and res["off_target"] == []


def test_a_find_elsewhere_on_the_document_is_not_a_find_near_the_place():
    manifest = {"split": "dev", "cases": [entry("d", [STATEMENT, SLIP], manipulations=[manip("D5", "02_payslip.pdf", HERE)])]}
    far = flag("pdf_overlay", ("D2", 1, (900, 900, 1000, 950)))
    on_other = flag("cross_name", ("D1", 1, (1, 1, 2, 2)))  # in the same case, on a document that was not changed
    res = score(manifest, {"d": case("d", ["01_statement.pdf", "02_payslip.pdf"], [far, on_other])}, {})
    m = res["methods"]["D5"]
    assert (m["found"], m["flagged_document"]) == (0, 1)
    (miss,) = res["misses"]
    assert "elsewhere" in miss["why"]
    assert [(o["case"], o["detector"]) for o in res["off_target"]] == [("d", "cross_name")]  # a flag that cites no changed document


def test_a_case_with_no_result_is_a_miss_and_is_counted_as_such():
    manifest = {"split": "dev", "cases": [entry("x", [STATEMENT], manipulations=[manip("D1", "01_statement.pdf", HERE)]),
                                          entry("y", [STATEMENT], genuine=True)]}
    res = score(manifest, {}, {})
    assert res["counts"]["no_result"] == 2 and res["methods"]["D1"]["found"] == 0
    assert "no result" in res["misses"][0]["why"] and res["genuine"]["documents"] == 0  # a genuine case that never ran says nothing


def test_extraction_classification_and_time_are_scored_by_layout_and_medium():
    slip = entry("e1", [SLIP, APP], genuine=True)
    slip["docs"][0]["fields"] = {"net_pay": "47200.00", "gross_earnings": "52000.00", "employee_name": "Meera K. Varghese"}
    slip["docs"][0]["rows"] = [{"earning_name": "Basic", "earning_amount": "30000.00", "deduction_name": None, "deduction_amount": None}]
    scan = entry("e2", [STATEMENT], medium="mild", layout="B", genuine=True)
    scan["docs"][0]["fields"] = {"opening_balance": "1000.00", "closing_balance": "2000.00"}

    def f(i, name, value, kind, row=None, conf=0.9):
        return Field(id=f"F{i}", doc="D1", name=name, raw=str(value), value=value, kind=kind, conf=conf, page=1, box=(0, 0, 1, 1), row=row)

    got = case("e1", ["02_payslip.pdf", "03_application.pdf"])
    got.documents[0].doc_type = "payslip"
    got.documents[1].doc_type = "unknown"  # the application was not recognised
    got.documents[0].fields = [f(1, "net_pay", "47200.00", "amount"), f(2, "gross_earnings", "52900.00", "amount"),
                               f(3, "line.earning_name", "Basic", "text", 1), f(4, "line.earning_amount", "30000.00", "amount", 1)]
    got2 = case("e2", ["01_statement.pdf"], pages=2)
    got2.documents[0].doc_type = "bank_statement"
    got2.documents[0].fields = [f(5, "opening_balance", "1000.00", "amount"), f(6, "closing_balance", "2900.00", "amount", conf=0.3)]
    res = score({"split": "dev", "cases": [slip, scan]}, {"e1": got, "e2": got2}, {"e1": 3.0, "e2": 8.0}, peak_rss_mb=512.0)
    rows = {(r["layout"], r["medium"], r["kind"]): r for r in res["extraction"]}
    amount = rows[("A", "digital", "amount")]
    assert (amount["n"], amount["correct"], amount["wrong"], amount["missing"]) == (3, 2, 1, 0)  # net pay and the cell right, gross wrong
    assert amount["trusted_wrong"] == 1  # ... and read at confidence 0.9, so nothing warned of it
    text = rows[("A", "digital", "text")]
    assert (text["n"], text["correct"], text["missing"]) == (2, 1, 1)  # the cell right, the name never read
    mild = rows[("B", "mild", "amount")]
    assert (mild["n"], mild["correct"], mild["wrong"], mild["trusted_wrong"], mild["accuracy"]) == (2, 1, 1, 0, 0.5)  # wrong, but at 0.3: doubted
    assert "wrong, trusted" in format_report(res) and res["low_conf"] == 0.6
    assert (res["classification"]["digital"]["n"], res["classification"]["digital"]["correct"]) == (2, 1)
    assert res["seconds_per_page"] == {"digital": pytest.approx(1.5), "scan": pytest.approx(4.0)}
    assert res["peak_rss_mb"] == 512.0


def test_the_report_lists_every_miss_and_false_flag_and_uses_no_verdict_word():
    res = score(*hand_made(), timings={"c1": 1.0}, peak_rss_mb=400.0)
    text = format_report(res)
    assert "c3" in text and "D2" in text and "limitation" in text  # the miss, with its reason
    assert "c6" in text and "cross_name" in text and "Minor mismatch" in text  # the false flag
    assert "IoU" in text and not VERDICT.search(text)


def scanned(c, *classes_of_each_document):
    """Give the documents of case c scanned pages (read by OCR) of the quality classes listed, one tuple of classes per document."""
    for d, classes in zip(c.documents, classes_of_each_document):
        d.pages = [Page(n=n, width=1654, height=2339, read_mode="ocr", quality_class=k) for n, k in enumerate(classes, 1)]
    return c


def test_the_report_counts_scanned_pages_by_quality_class_and_medium():
    files = ["01_statement.pdf", "02_payslip.pdf"]
    manifest = {"split": "dev", "cases": [entry(n, [STATEMENT, SLIP], medium=m, genuine=True) for n, m in
                                          (("q1", "150dpi"), ("q2", "150dpi"), ("q3", "mild"), ("q4", "digital"), ("q5", "120dpi"))]}
    cases = {"q1": scanned(case("q1", files), ("good", "good"), ("degraded",)), "q2": scanned(case("q2", files), ("good",), ("poor",)),
             "q3": scanned(case("q3", files), ("good",), ("good",)), "q4": case("q4", files)}  # q4 has text-layer pages, q5 never ran
    res = score(manifest, cases, {})
    assert res["page_quality"] == {"mild": {"pages": 2, "good": 2, "degraded": 0, "poor": 0},
                                   "150dpi": {"pages": 5, "good": 3, "degraded": 1, "poor": 1}}  # no row for digital or for a case that did not run
    text = format_report(res)
    assert "| mild | 2 | 2 | 0 | 0 |" in text and "| 150dpi | 5 | 3 | 1 | 1 |" in text and not VERDICT.search(text)
    assert text.index("| mild | 2 |") < text.index("| 150dpi | 5 |")  # in the order of the media, not alphabetical


def test_splits_are_disjoint():
    dev, test = plan_cases("dev", 60, 0), plan_cases("test", 60, 0)
    assert not {c["seed"] for c in dev} & {c["seed"] for c in test}
    assert {c["method"] for c in dev if c["method"]} == set(METHODS) - TEST_ONLY and TEST_ONLY == {"D3", "S2"}
    assert {c["method"] for c in test if c["method"]} == set(METHODS)
    assert {c["layout"] for c in dev} == {"A"} and {c["layout"] for c in test} == {"A", "B"}
    last_dev = plan_cases("dev", 10, SPLIT_SPAN - 10)
    assert not {c["seed"] for c in last_dev} & {c["seed"] for c in plan_cases("test", 10, 0)}  # even at the far end of the dev range
    with pytest.raises(ValueError):
        plan_cases("dev", 10, SPLIT_SPAN - 9)  # would run into the next split's seeds


def test_the_plan_balances_methods_and_media():
    plan = plan_cases("dev", 66, 0)
    assert [c["case"] for c in plan] == [f"dev-{i:04d}" for i in range(66)] and plan == plan_cases("dev", 66, 0)
    counts = {m: sum(c["method"] == m for c in plan) for m in set(METHODS) - TEST_ONLY}
    assert max(counts.values()) - min(counts.values()) <= 1 and min(counts.values()) >= 4
    assert sum(c["genuine"] for c in plan) == 22 and all((c["method"] is None) == c["genuine"] for c in plan)
    medium = {m: sum(c["medium"] == m for c in plan) for m in ("digital", "mild", "150dpi", "120dpi")}
    assert min(medium.values()) >= 3 and medium["120dpi"] <= medium["150dpi"] <= medium["mild"]
    assert all(c["medium"] == "digital" for c in plan if c["method"] in ("D1", "D2", "D4", "D5"))
    assert all(c["medium"] != "digital" for c in plan if c["method"] == "S1")


def test_a_small_dev_split_is_written_with_a_manifest_that_agrees_with_its_files(tmp_path):
    out = tmp_path / "dev"
    manifest_path = build_split("dev", out, 8, 0)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_path == out / "manifest.json" and manifest["split"] == "dev" and len(manifest["cases"]) == 8
    for c in manifest["cases"]:
        names = [d["file"] for d in c["docs"]]
        assert sorted(p.name for p in (out / c["case"]).iterdir()) == sorted(names)
        for d in c["docs"]:
            data = (out / c["case"] / d["file"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == d["sha256"]
            assert d["file"].endswith(".pdf" if c["medium"] == "digital" else ".jpg")
        for m in c["manipulations"]:
            assert m["doc"] in names and set(m["also"]) <= set(names)
            assert (m["box"] is None) == (m["method"] in ("D4", "C1", "C2", "C3", "C4", "C5")), m
        assert c["genuine"] == (not c["manipulations"])
    d1 = next(c for c in manifest["cases"] if [m["method"] for m in c["manipulations"]] == ["D1"])
    target = d1["manipulations"][0]["doc"]
    assert (out / d1["case"] / target).read_bytes().count(b"%%EOF") == 2  # the original revision is still inside


def test_the_same_seeds_give_the_same_files(tmp_path):
    a, b = build_split("dev", tmp_path / "a", 12, 5), build_split("dev", tmp_path / "b", 12, 5)
    assert a.read_bytes() == b.read_bytes()
    for p in sorted((tmp_path / "a").rglob("*.*")):
        assert p.read_bytes() == (tmp_path / "b" / p.relative_to(tmp_path / "a")).read_bytes(), p


def test_a_small_dev_split_runs_end_to_end_and_the_report_is_written(tmp_path):
    res = evaluate("dev", 3, 0, tmp_path / "eval")  # one D1 case, one D2 case, one genuine case: all digital, no OCR
    assert (tmp_path / "eval" / "dev.md").is_file() and res["counts"]["cases"] == 3 and res["counts"]["no_result"] == 0
    assert res["classification"]["digital"]["correct"] == res["classification"]["digital"]["n"] == 9
    assert res["methods"]["D1"]["n"] == 1 and res["genuine"]["cases"] == 1
    assert not VERDICT.search((tmp_path / "eval" / "dev.md").read_text(encoding="utf-8"))


def test_pipeline_does_not_read_ground_truth():
    hits = [p for p in SRC.rglob("*") if p.is_file() and p.suffix in {".py", ".json", ".toml", ".md", ".html", ".js", ".css", ".txt"}
            and re.search(r"manifest|datagen", p.read_text(encoding="utf-8", errors="replace"), re.I)]
    assert hits == []
