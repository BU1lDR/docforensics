"""The files for measuring the raw file-structure check (datagen/structure_pack.py): the plan, the builders, and what the check says of each file."""
import hashlib
import json

import pytest

from datagen import structure_pack as pack
from tests.test_structure import detect

DEV = pack.plan_cases("ext-dev", len(pack.KINDS))


def test_the_plan_cycles_through_the_kinds_with_seeds_of_its_own():
    assert [p["kind"] for p in DEV] == list(pack.KINDS) and len(pack.KINDS) == 12
    assert [p["seed"] for p in DEV] == list(range(3_300_000, 3_300_012))
    assert [p["seed"] for p in pack.plan_cases("ext-test", 3)] == [4_300_000, 4_300_001, 4_300_002]  # apart from X (+0), E (+100000) and H (+200000)
    assert [p["kind"] for p in pack.plan_cases("ext-dev", 3, start=12)] == list(pack.KINDS[:3])
    assert pack.plan_cases("ext-dev", 1, start=12)[0]["layout"] != DEV[0]["layout"]
    for bad in (("dev", 1, 0), ("ext-dev", 1, 10_000), ("ext-dev", 1, -1)):
        with pytest.raises(ValueError):
            pack.plan_cases(*bad)


@pytest.mark.parametrize("i", range(len(pack.KINDS)), ids=pack.KINDS)
def test_a_case_is_built_the_same_way_twice(i):
    (a, ea), (b, eb) = pack.build_case(DEV[i]), pack.build_case(DEV[i])
    assert a == b and ea == eb and ea["sha256"] == hashlib.sha256(a).hexdigest()


@pytest.mark.parametrize("p", DEV, ids=[p["kind"] for p in DEV])
def test_the_check_shows_what_each_file_was_planted_with_and_nothing_else(tmp_path, p):
    data, entry = pack.build_case(p)
    shown = sorted(f.title for f in detect(tmp_path, data) if f.fclass == "observation")
    assert shown == sorted(entry["expect"]), entry["note"]
    assert bool(entry["expect"]) == (p["kind"] in pack.PLANTED)


def test_the_ext_test_pack_is_written_and_the_check_is_not_run_on_it(tmp_path):
    manifest = json.loads(pack.build_split("ext-test", tmp_path, 12).read_text(encoding="utf-8"))
    assert manifest["split"] == "ext-test" and manifest["pack"] == "structure" and len(manifest["cases"]) == 12
    for e in manifest["cases"]:
        assert hashlib.sha256((tmp_path / e["case"] / e["file"]).read_bytes()).hexdigest() == e["sha256"]


def test_no_file_of_the_pack_carries_a_script_or_a_launch_key(tmp_path):
    pack.build_split("ext-dev", tmp_path, 12)
    for path in tmp_path.glob("*/document.pdf"):
        raw = path.read_bytes()
        assert not any(k in raw for k in (b"/JavaScript", b"/JS", b"/Launch", b"/AA")), path
