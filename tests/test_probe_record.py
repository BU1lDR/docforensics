"""The record of the probe (docs/probe.md). eval/probe/digital.csv and raster.csv hold one row for each edit, and the tables of the document
are counted from them here, so the document cannot drift from the files. The probe is a development measurement on synthetic files made by
the tool's author; it is not capability evidence and no row of the matrix cites this file."""
import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "probe.md").read_text(encoding="utf-8")


def load(name: str) -> list[dict]:
    with open(ROOT / "eval" / "probe" / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


DIGITAL, RASTER = load("digital.csv"), load("raster.csv")
M5 = [r for r in RASTER if r["kind"] == "M5"]
CONTROLS = [r for r in RASTER if r["kind"] == "control"]


def total(rows: list[dict], column: str) -> int:
    return sum(int(r[column]) for r in rows)


def names(cell: str) -> list[str]:
    """The checks named in a cell: 'a b' or 'a:observation b:inconsistency'."""
    return [c.split(":")[0] for c in cell.split()]


def table(pattern: str) -> list[tuple]:
    """What the groups of a pattern catch on each matching line of the document."""
    return [m.groups() for m in re.finditer(pattern, DOC, re.M)]


def test_the_record_has_one_row_for_each_edit():
    assert len({r["id"] for r in DIGITAL}) == len(DIGITAL) == 588
    assert Counter(r["kind"] for r in DIGITAL) == {"M1": 168, "M2": 144, "M3": 96, "M4": 160, "M6": 20}
    assert len(M5) == 108 and len(CONTROLS) == 18
    assert all(r[c] in ("0", "1") for r in DIGITAL for c in ("expected_miss", "found_first", "located_first", "found_now", "located_now"))
    assert all(r["located_now"] <= r["found_now"] and r["located_first"] <= r["found_first"] for r in DIGITAL)  # a location is of a find


def test_table_1_is_counted_from_the_record():
    columns = ("found_first", "found_now", "located_first", "located_now", "false_now")
    shown = {kind: tuple(int(x) for x in cells.split(" | ")) for kind, cells in table(r"^\| (M\d|All) \| (\d+(?: \| \d+){5}) \|$")}
    assert set(shown) == {"M1", "M2", "M3", "M4", "M6", "All"}
    for kind, cells in shown.items():
        rows = DIGITAL if kind == "All" else [r for r in DIGITAL if r["kind"] == kind]
        assert cells == (len(rows), *(total(rows, c) for c in columns)), kind


def test_the_table_of_variants_is_counted_from_the_record():
    shown = sorted((kind, *(int(x) for x in cells)) for kind, _, *cells in table(r"^\| (M\d) ([^|]+?) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$"))
    groups: dict[tuple, list[dict]] = {}
    for r in DIGITAL:
        groups.setdefault((r["kind"], r["variant"]), []).append(r)
    counted = sorted((kind, len(rs), total(rs, "found_now"), total(rs, "located_now"), total(rs, "found_first")) for (kind, _), rs in groups.items())
    assert shown == counted and len(shown) == 29
    assert all(len({r["expected_miss"] for r in rs}) == 1 for rs in groups.values())  # an expected miss is a property of the kind of edit
    marked = sum(int(m.group(1)) for m in re.finditer(r"^\| M\d [^|]*\(expected miss\)[^|]* \| (\d+) \|", DOC, re.M))
    assert marked == total(DIGITAL, "expected_miss") == 88


def test_the_headline_counts():
    expected = [r for r in DIGITAL if r["expected_miss"] == "1"]
    rest = [r for r in DIGITAL if r["expected_miss"] == "0"]
    assert len(expected) == 88 and total(expected, "found_now") == total(expected, "found_first") == 0
    assert (len(rest), total(rest, "found_now"), total(rest, "located_now")) == (500, 473, 413)
    assert len([r for r in DIGITAL if r["found_now"] == "0"]) == 115  # the 88 and 27 others
    assert total(DIGITAL, "false_now") == 0
    assert not [r for r in DIGITAL if int(r["found_now"]) < int(r["found_first"]) or int(r["located_now"]) < int(r["located_first"])]
    assert "Of the other 500, 473 were found, 27 missed and 413 located" in DOC and "115 edits: the 88 expected misses and 27 others" in DOC


def test_the_checks_that_found_them_are_counted_from_the_record():
    shown = {name: (int(count), {k: int(x) for k, x in re.findall(r"(M\d) (\d+)", kinds)})
             for name, count, kinds in table(r"^\| `(\w+)` \([^)]*\) \| (\d+) \| ([^|]*) \|$")}
    count, by_kind = Counter(), {}
    for r in DIGITAL:
        for name in set(names(r["detectors_now"])):
            count[name] += 1
            by_kind.setdefault(name, Counter())[r["kind"]] += 1
    assert len(shown) == 8 and shown == {name: (count[name], dict(by_kind[name])) for name in count}


def test_the_font_check_figures_are_counted_from_the_record():
    """What the record holds of the font check: how many numbers set in the built-in font it flagged. That the 42 stood in a group it
    compares is read from the edited files, not from the record."""
    naive = [r for r in DIGITAL if "naive" in r["variant"]]
    flagged = [r for r in naive if "pdf_fonts" in names(r["detectors_now"])]
    outside = [r for r in naive if "pdf_fonts" not in names(r["detectors_now"])]
    assert (len(naive), len(flagged), len(outside), total(outside, "found_now")) == (77, 42, 35, 34)
    assert Counter(r["variant"].split("-")[0] for r in outside) == {"ps_net": 24, "ap_income": 6, "st_credit": 3, "stmt": 2}
    own_font = [r for r in DIGITAL if r["kind"] == "M1" and "redact-same" in r["variant"]]
    assert len(own_font) == 96 and not [r for r in own_font if "pdf_fonts" in names(r["detectors_now"])]
    for words in ("Of 77 numbers", "all 42 were flagged", "the 35 that did not", "found 34 of them", "0 of 96"):
        assert words in DOC, words


def test_the_scanned_tables_are_counted_from_the_record():
    assert (len(M5), total(M5, "found"), total(M5, "located"), total(M5, "false")) == (108, 88, 88, 0)
    assert all(r["found"] == r["located"] for r in M5)

    def found(fits) -> str:
        return str(total([r for r in M5 if fits(r["variant"])], "found"))

    by_target = " / ".join(found(lambda v, t=t: v.startswith(t + "-")) for t in ("ap_income", "ps_net", "st_credit"))
    by_method = " / ".join(found(lambda v, m=m: f"-{m}-" in v) for m in ("ttf", "hershey"))
    by_medium = " / ".join(found(lambda v, m=m: v.endswith("-" + m)) for m in ("150-png", "200-png", "200-jpg"))
    assert (by_target, by_method, by_medium) == ("31 / 31 / 26", "44 / 44", "31 / 29 / 28")
    for line in ("| All | 108 | 88 | 88 | 0 |", "| 36 each | 31 / 31 / 26 | 31 / 31 / 26 | 0 |", "| 54 each | 44 / 44 | 44 / 44 | 0 |",
                 "| 36 each | 31 / 29 / 28 | 31 / 29 / 28 | 0 |"):
        assert line in DOC, line
    # all 88 found by arithmetic and cross-document checks, none by a scan check
    assert Counter(c for r in M5 if r["found"] == "1" for c in names(r["detectors"])) == {
        "cross_income": 31, "payslip_sums": 31, "statement_balance": 26, "cross_net_pay": 3}


def test_the_controls_carry_one_false_inconsistency_and_no_scan_observation():
    flagged = [(r["id"], r["detectors"]) for r in CONTROLS if r["detectors"]]
    assert flagged == [("M5-control-150-png-P5000000", "statement_balance:inconsistency")]
    assert "carries a false `statement_balance` inconsistency" in DOC
