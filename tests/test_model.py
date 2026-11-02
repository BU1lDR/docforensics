import re

import pytest
from pydantic import ValidationError

from docforensics.config import Thresholds
from docforensics.model import Case, Document, Evidence, Field, Finding, Page, Word
from docforensics.store import CaseDir, load_case, save_case


def make_case() -> Case:
    word = Word(id="D1-p1-w1", text="52,000.00", box=(10, 20, 110, 40), font="Helvetica", size=9.0, pt_box=(5, 10, 55, 20))
    field = Field(id="D1-f1", doc="D1", name="net_pay", raw="52,000.00", value="52000.00", kind="amount", conf=0.97,
                  word_ids=[word.id], page=1, box=word.box)
    page = Page(n=1, width=1654, height=2339, image_path="pages/D1-1.png", words=[word])
    doc = Document(id="D1", sha256="ab" * 32, filename="slip.pdf", stored_path="files/" + "ab" * 32 + ".pdf",
                   kind="pdf-digital", pages=[page], fields=[field])
    ev = [Evidence(doc="D1", page=1, box=word.box, note="value", field_id=field.id, value="52000.00"),
          Evidence(doc="D2", page=1, box=(1, 2, 3, 4), note="bank credit")]
    f = Finding(id="F-001", fclass="inconsistency", detector="net_pay_vs_bank", family="cross_document",
                title="Net pay differs from the bank credit", conf=0.9, evidence=ev)
    return Case(id="C-20261102-120000-ab12", created="2026-11-02T12:00:00+00:00", documents=[doc], findings=[f])


def test_case_round_trip(tmp_path):
    cd = CaseDir.create(tmp_path)
    case = make_case()
    save_case(case, cd)
    assert load_case(cd) == case
    assert len(load_case(cd).findings[0].evidence) == 2


def test_save_leaves_no_temp_file(tmp_path):
    cd = CaseDir.create(tmp_path)
    save_case(make_case(), cd)
    assert sorted(p.name for p in cd.root.iterdir() if p.is_file()) == ["case.json"]


def test_finding_rejects_unknown_class_and_status():
    base = dict(detector="d", family="visual", title="t")
    with pytest.raises(ValidationError):
        Finding(fclass="fraud", **base)
    f = Finding(fclass="observation", **base)
    with pytest.raises(ValidationError):
        f.status = "forged"


def test_thresholds_defaults_match_design():
    th = Thresholds()
    assert (th.low_conf, th.amount_abs, th.amount_rel, th.name_sim) == (0.6, 1.0, 0.005, 0.85)
    assert (th.max_file_bytes, th.max_pages, th.max_docs) == (10_000_000, 20, 10)


def test_thresholds_toml_override(tmp_path):
    p = tmp_path / "t.toml"
    p.write_text("low_conf = 0.7\n", encoding="utf-8")
    th = Thresholds.from_toml(p)
    assert th.low_conf == 0.7 and th.name_sim == 0.85
    assert th.as_dict()["low_conf"] == 0.7


def test_thresholds_toml_rejects_unknown_key(tmp_path):
    p = tmp_path / "t.toml"
    p.write_text("low_confidence = 0.7\n", encoding="utf-8")
    with pytest.raises(ValueError, match="low_confidence"):
        Thresholds.from_toml(p)


def test_case_dir_layout(tmp_path):
    cd = CaseDir.create(tmp_path)
    assert re.fullmatch(r"C-\d{8}-\d{6}-[0-9a-f]{4}", cd.id)
    assert cd.root.parent == tmp_path / "cases"
    assert cd.files.is_dir() and cd.pages.is_dir() and cd.crops.is_dir()
    assert CaseDir.open(tmp_path, cd.id).root == cd.root


@pytest.mark.parametrize("bad", ["..\\..\\x", "C-1/../..", "../x", "", "C-20261102-120000-ab12/x"])
def test_open_rejects_traversal_ids(tmp_path, bad):
    with pytest.raises(ValueError):
        CaseDir.open(tmp_path, bad)


def test_open_unknown_case_is_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        CaseDir.open(tmp_path, "C-20261102-120000-ab12")
