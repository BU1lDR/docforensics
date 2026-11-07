"""The cases for measuring the declared-EMI check (datagen/emi_pack.py): the plan, the builders, and what the check says of each kind."""
import hashlib
import json
from decimal import Decimal

import pytest

from datagen import emi_pack as pack
from docforensics.checks.cross import is_instalment
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case

DEV = pack.plan_cases("ext-dev", len(pack.KINDS))
TH = Thresholds()


def test_the_plan_cycles_through_the_kinds_the_layouts_and_the_media_with_seeds_of_its_own():
    assert [p["kind"] for p in DEV] == list(pack.KINDS) and len(pack.KINDS) == 11
    assert [p["seed"] for p in DEV] == list(range(3_400_000, 3_400_011))  # apart from X (+0), E (+100000), H (+200000), structure (+300000)
    assert [p["seed"] for p in pack.plan_cases("ext-test", 3)] == [4_400_000, 4_400_001, 4_400_002]
    assert [p["case"] for p in DEV[:2]] == ["ext-dev-m-0000", "ext-dev-m-0001"]
    plan = pack.plan_cases("ext-dev", 44)
    assert {(p["layout"], p["medium"]) for p in plan} == {("A", "digital"), ("B", "digital"), ("A", "scan"), ("B", "scan")}
    assert [(p["layout"], p["medium"]) for p in (plan[0], plan[11], plan[22], plan[33])] == [("A", "digital"), ("B", "digital"), ("A", "scan"), ("B", "scan")]
    assert [p["kind"] for p in pack.plan_cases("ext-dev", 3, start=11)] == list(pack.KINDS[:3])
    for bad in (("dev", 1, 0), ("ext-dev", 1, 10_000), ("ext-dev", 1, -1)):
        with pytest.raises(ValueError):
            pack.plan_cases(*bad)


@pytest.mark.parametrize("i", range(len(pack.KINDS)), ids=pack.KINDS)
def test_a_case_is_built_the_same_way_twice(i):
    (a, ea), (b, eb) = pack.build_case(DEV[i]), pack.build_case(DEV[i])
    assert a == b and ea == eb
    assert {n: hashlib.sha256(d).hexdigest() for n, d in a.items()} == ea["sha256"] and set(a) == {"application.pdf", "statement.pdf"}


def test_a_scanned_case_is_two_jpegs():
    p = next(c for c in pack.plan_cases("ext-dev", 44) if c["medium"] == "scan")
    files, entry = pack.build_case(p)
    assert set(files) == {"application.jpg", "statement.jpg"} == set(entry["files"]) and all(d[:2] == b"\xff\xd8" for d in files.values())


def _numbers(entry):
    return Decimal(entry["declared"]), [Decimal(x["amount"]) for x in entry["set"] if x["instalment"]]


@pytest.mark.parametrize("layout", ["A", "B"])
def test_each_kind_sets_the_rows_and_the_declared_figure_as_its_description_says(layout):
    seen = set()
    for p in [dict(p, layout=layout, medium="digital") for p in pack.plan_cases("ext-dev", 11 * 6)]:  # six seeds of each kind: the amounts change with the seed
        _, e = pack.build_case(p)
        declared, paid = _numbers(e)
        total, kind = sum(paid), e["kind"]
        seen.add(kind)
        tol = max(Decimal(1), total / 10)
        if kind == "none":
            assert not e["set"]
        elif kind == "match":
            assert len(paid) == 1 and declared == total
        elif kind == "rounded":
            assert len(paid) == 1 and Decimal(0) < total - declared <= Decimal(500) and total - declared <= tol and declared % 1000 == 0
        elif kind == "two-loans":
            assert len(paid) == 2 and declared == total
        elif kind == "declared-higher":
            assert len(paid) == 1 and declared == total + 5000
        elif kind in ("fee-not-emi", "lookalike"):
            assert len(e["set"]) == 3 and not paid and not any(is_instalment(x["narration"]) for x in e["set"])
        elif kind == "under-zero":
            assert len(paid) == 1 and declared == 0 and total >= 2000
        elif kind == "under-part":
            assert len(paid) == 2 and 0 < declared < total and total - declared > tol
        elif kind == "under-some":
            assert len(paid) == 1 and 0 < declared < total and total - declared > tol
        elif kind == "lender-only":
            assert len(e["set"]) == 1 and not paid and declared == 0 and not is_instalment(e["set"][0]["narration"])
        assert bool(e["expect"]) == (kind in pack.PLANTED)
        assert (e["total"] is not None) == (kind in pack.PLANTED)
    assert seen == set(pack.KINDS)


def test_the_statement_still_adds_up_after_the_rows_are_set():
    """Setting a debit changes every balance after it and the closing balance, so no other check has a reason to speak."""
    for p in pack.plan_cases("ext-dev", 22):
        application, statement, entry = pack.draw_case(p)
        rows = statement.truth["rows"]
        bal = Decimal(statement.truth["fields"]["opening_balance"])
        for r in rows:
            bal += Decimal(r["credit"] or 0) - Decimal(r["debit"] or 0)
            assert Decimal(r["balance"]) == bal >= 0, (p["case"], r)
        assert Decimal(statement.truth["fields"]["closing_balance"]) == bal
        assert application.truth["fields"]["existing_emi"] == entry["declared"]
        for x in entry["set"]:
            assert rows[x["row"] - 1]["description"] == x["narration"] and rows[x["row"] - 1]["debit"] == x["amount"]


def test_the_narrations_are_what_the_kinds_say_they_are():
    for p in pack.plan_cases("ext-dev", 44):
        _, e = pack.build_case(dict(p, medium="digital"))
        for x in e["set"]:
            assert x["instalment"] == (e["kind"] not in ("fee-not-emi", "lookalike", "lender-only")) == is_instalment(x["narration"]), x


@pytest.mark.parametrize("p", DEV, ids=[p["kind"] for p in DEV])
def test_the_check_shows_what_each_kind_was_planted_with_and_nothing_else(tmp_path, p):
    files, entry = pack.build_case(p)
    _, cd, _ = create_case(tmp_path / "data", sorted(files.items()), TH)
    mine = [f for f in run_case(cd, TH).findings if f.detector == "cross_emi" and f.fclass == "inconsistency"]
    shown = sorted(f.title for f in mine)
    if p["kind"] in pack.BLIND:
        assert shown == [] and entry["expect"] == [pack.TITLE], entry["note"]  # the gap is there and the check cannot see it
    else:
        assert shown == sorted(entry["expect"]), entry["note"]
    for f in mine:
        assert f"INR {entry['total']}" in f.detail


def test_the_ext_test_pack_is_written_and_the_check_is_not_run_on_it(tmp_path):
    manifest = json.loads(pack.build_split("ext-test", tmp_path, 22).read_text(encoding="utf-8"))
    assert manifest["split"] == "ext-test" and manifest["pack"] == "emi" and len(manifest["cases"]) == 22
    for e in manifest["cases"]:
        for name, digest in e["sha256"].items():
            assert hashlib.sha256((tmp_path / e["case"] / name).read_bytes()).hexdigest() == digest
