"""Relationship view: the names, addresses, employers and account numbers that stand for one thing across documents, and the findings
that touch them. Hand-built cases, where every box is placed on purpose; what counts as one thing is what the cross-document checks
count as the same (SAME or FORM), so the view cannot disagree with them."""
import copy

import pytest

from docforensics.findings import field_evidence
from docforensics.model import Case, Document, Evidence, Field, Finding, Page
from docforensics.relations import build_relations

NAME, EMPLOYER, ACCOUNT = (100.0, 100.0, 300.0, 130.0), (100.0, 300.0, 300.0, 330.0), (100.0, 500.0, 300.0, 530.0)
ELSEWHERE = (900.0, 900.0, 950.0, 950.0)


def fld(doc, name, value, box, role="", conf=0.95):
    return Field(id=f"{doc}-{name}", doc=doc, name=name, raw=value or "", value=value, kind="text", conf=conf, word_ids=[f"{doc}-w1"],
                 page=1, box=box, role=role)


def document(id, filename, *fields):
    return Document(id=id, sha256=id, filename=filename, stored_path="", doc_type="payslip", type_conf=1.0,
                    pages=[Page(n=1, width=1654, height=2339, quality_class="text-layer")], fields=list(fields))


def finding(n, fclass, detector, family, *evidence, title=None, cluster=None):
    return Finding(id=f"F-{n:03d}", fclass=fclass, detector=detector, family=family, title=title or f"{detector} title",
                   evidence=list(evidence), cluster=cluster)


def at(box, doc="D2", note="somewhere"):
    """Evidence that points at a place and not at an extracted field, as the visual detectors do."""
    return Evidence(doc=doc, page=1, box=box, note=note)


def three_documents():
    """A statement, a payslip and an application of one person. The statement spells the name with one letter changed; the payslip and
    the application write the same name in another order; the account number is spaced differently on the statement; the employer's
    legal form is written out on the application."""
    return [
        document("D1", "statement.pdf", fld("D1", "account_holder", "Divyu C. Menon", NAME, "name"), fld("D1", "account_no", "1234 5678", ACCOUNT, "account")),
        document("D2", "payslip.pdf", fld("D2", "employee_name", "Divya C. Menon", NAME, "name"),
                 fld("D2", "employer", "Alpha Test Pvt Ltd", EMPLOYER, "employer"), fld("D2", "account_no", "12345678", ACCOUNT, "account")),
        document("D3", "application.pdf", fld("D3", "applicant_name", "MENON, Divya C", NAME, "name"),
                 fld("D3", "employer", "Alpha Test Private Limited", EMPLOYER, "employer")),
    ]


def case_of(docs, *findings):
    return Case(id="C-test", created="2026-11-05T00:00:00Z", documents=docs, findings=list(findings))


def labelled(rel):
    """{label: entity}, for a reading that does not depend on the numbering."""
    return {e["label"]: e for e in rel["entities"]}


def test_a_value_written_alike_in_two_documents_is_one_entity():
    rel = build_relations(case_of(three_documents()))
    divya = labelled(rel)["Divya C. Menon"]
    assert divya["role"] == "name" and divya["writings"] == ["Divya C. Menon", "MENON, Divya C"]  # the checks grade these two as the same name
    assert [(m["doc"], m["file"], m["field"]) for m in divya["mentions"]] == [("D2", "payslip.pdf", "D2-employee_name"), ("D3", "application.pdf", "D3-applicant_name")]
    employer = labelled(rel)["Alpha Test Pvt Ltd"]
    assert [m["doc"] for m in employer["mentions"]] == ["D2", "D3"]  # the legal form does not make another employer
    account = labelled(rel)["1234 5678"]
    assert [m["doc"] for m in account["mentions"]] == ["D1", "D2"] and account["writings"] == ["1234 5678", "12345678"]


def test_a_value_that_differs_is_another_entity_and_the_numbering_follows_the_documents():
    rel = build_relations(case_of(three_documents()))
    assert [(e["id"], e["role"], e["label"]) for e in rel["entities"]] == [
        ("E1", "name", "Divyu C. Menon"), ("E2", "account", "1234 5678"), ("E3", "name", "Divya C. Menon"), ("E4", "employer", "Alpha Test Pvt Ltd")]


def test_the_same_words_under_two_roles_are_two_entities():
    docs = [document("D1", "a.pdf", fld("D1", "holder", "Alpha Test", NAME, "name")),
            document("D2", "b.pdf", fld("D2", "employer", "Alpha Test", EMPLOYER, "employer"))]
    assert [(e["role"], e["label"]) for e in build_relations(case_of(docs))["entities"]] == [("name", "Alpha Test"), ("employer", "Alpha Test")]


@pytest.mark.parametrize("name, value, role", [("empty", "", "name"), ("unread", None, "name"), ("only punctuation", " .- ", "name"),
                                              ("no role", "Divya C. Menon", ""), ("not an entity", "52000.00", "amount")])
def test_a_field_with_no_value_or_that_is_not_an_entity_is_left_out(name, value, role):
    docs = [document("D1", "a.pdf", fld("D1", "x", value, NAME, role))]
    rel = build_relations(case_of(docs))
    assert rel["entities"] == [] and rel["documents"] == [{"id": "D1", "file": "a.pdf", "type": "payslip", "entities": []}]


def test_a_mention_says_where_the_value_is_and_how_sure_the_reading_is():
    docs = [document("D1", "a.pdf", fld("D1", "holder", "Divya C. Menon", NAME, "name", conf=0.41))]
    (e,) = build_relations(case_of(docs))["entities"]
    assert e["mentions"] == [{"doc": "D1", "file": "a.pdf", "field": "D1-holder", "name": "holder", "page": 1, "box": list(NAME),
                              "conf": 0.41, "value": "Divya C. Menon"}]


def test_a_finding_that_cites_fields_touches_every_entity_they_hold():
    docs = three_documents()
    name = [d.fields[0] for d in docs]
    mismatch = finding(1, "inconsistency", "cross_name", "cross_document", *(field_evidence(f, "name") for f in name), title="Minor mismatch: name differs between documents")
    rel = build_relations(case_of(docs, mismatch))
    assert rel["findings"] == [{"id": "F-001", "class": "inconsistency", "title": "Minor mismatch: name differs between documents",
                                "detector": "cross_name", "cluster": None, "entities": ["E1", "E3"]}]
    assert [(e["id"], e["findings"]) for e in rel["entities"]] == [("E1", ["F-001"]), ("E2", []), ("E3", ["F-001"]), ("E4", [])]


def test_a_writing_that_differs_only_in_form_touches_one_entity():
    docs = three_documents()
    form = finding(1, "observation", "cross_name", "cross_document", field_evidence(docs[1].fields[0]), field_evidence(docs[2].fields[0]))
    (node,) = build_relations(case_of(docs, form))["findings"]
    assert node["entities"] == ["E3"]


def test_a_finding_that_lies_over_a_field_touches_its_entity_and_one_far_away_touches_none():
    docs = three_documents()
    over = finding(1, "observation", "pdf_fonts", "visual", at((110.0, 105.0, 290.0, 125.0)))
    away = finding(2, "observation", "pdf_fonts", "visual", at(ELSEWHERE))
    rel = build_relations(case_of(docs, over, away))
    assert [(n["id"], n["entities"]) for n in rel["findings"]] == [("F-001", ["E3"])]  # a finding that touches no entity is not in the view


def test_headlines_and_limitations_are_not_findings_of_the_view():
    docs = three_documents()
    cites = [field_evidence(docs[1].fields[0])]
    real = finding(1, "inconsistency", "cross_name", "cross_document", *cites, cluster="F-002")
    head = finding(2, "potential_manipulation", "link", "cluster", *cites)
    gap = finding(3, "processing_limitation", "cross_checks", "limitation", *cites)
    rel = build_relations(case_of(docs, real, head, gap))
    assert [(n["id"], n["cluster"]) for n in rel["findings"]] == [("F-001", "F-002")]
    assert labelled(rel)["Divya C. Menon"]["findings"] == ["F-001"]


def test_a_document_lists_the_entities_it_mentions_once_each_in_order():
    rel = build_relations(case_of(three_documents()))
    assert [(d["id"], d["file"], d["entities"]) for d in rel["documents"]] == [
        ("D1", "statement.pdf", ["E1", "E2"]), ("D2", "payslip.pdf", ["E3", "E4", "E2"]), ("D3", "application.pdf", ["E3", "E4"])]


def test_a_value_written_twice_in_one_document_is_two_mentions_of_one_entity():
    docs = [document("D1", "a.pdf", fld("D1", "holder", "Divya C. Menon", NAME, "name"), fld("D1", "signatory", "Divya C Menon", EMPLOYER, "name"))]
    rel = build_relations(case_of(docs))
    (e,) = rel["entities"]
    assert [m["field"] for m in e["mentions"]] == ["D1-holder", "D1-signatory"] and rel["documents"][0]["entities"] == ["E1"]


def test_building_the_view_changes_nothing_and_gives_the_same_answer_twice():
    docs = three_documents()
    case = case_of(docs, finding(1, "inconsistency", "cross_name", "cross_document", *(field_evidence(d.fields[0]) for d in docs)))
    before = copy.deepcopy(case)
    first = build_relations(case)
    assert case == before and build_relations(case) == first


def test_a_case_with_no_documents_has_an_empty_view():
    assert build_relations(case_of([])) == {"entities": [], "findings": [], "documents": []}
