"""Linking (Task 18, design 7.6): findings that share a field, a place on a page or an entity are grouped, and a group in which two
or more independent kinds of check fired becomes a potential-manipulation candidate. The grouping is tested on hand-built cases,
where every box is placed on purpose, and on two drawn manipulations that go through the whole pipeline."""
from pathlib import Path

import pytest

from datagen.fictional import identity
from datagen.layouts import money
from datagen.layouts.payslip import draw_payslip
from datagen.layouts.application import draw_application
from datagen.layouts.statement import draw_statement
from datagen.manipulate import d1_incremental_edit
from docforensics import link as linking
from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.findings import doc_evidence, field_evidence, limitation
from docforensics.ingest import create_case
from docforensics.link import cluster_headline, link_findings
from docforensics.model import Case, Document, Evidence, Field, Finding, Page
from docforensics.pipeline import Ctx, run_case
from docforensics.store import CaseDir
from tests.helpers import iou

TH = Thresholds()
NET = (100.0, 400.0, 260.0, 430.0)  # the net pay value on the payslip
CREDIT = (500.0, 900.0, 640.0, 930.0)  # a credit on the statement


# --- hand-built cases

def fld(doc, name, value, box, row=None, role=""):
    return Field(id=f"{doc}-{name}", doc=doc, name=name, raw=value or "", value=value, kind="text", conf=0.95, word_ids=[f"{doc}-w1"],
                 page=1, box=box, row=row, role=role)


def document(id, filename, *fields):
    return Document(id=id, sha256=id, filename=filename, stored_path="", doc_type="payslip", type_conf=1.0,
                    pages=[Page(n=1, width=1654, height=2339, quality_class="text-layer")], fields=list(fields))


def at(box, note="", value=None, doc="D2", page=1):
    """Evidence that points at a place and not at an extracted field, as the visual detectors do."""
    return Evidence(doc=doc, page=page, box=box, note=note, value=value)


def finding(n, fclass, detector, family, *evidence, title=None, conf=1.0):
    return Finding(id=f"F-{n:03d}", fclass=fclass, detector=detector, family=family, title=title or f"{detector} title", conf=conf,
                   evidence=list(evidence))


def built(*findings, fields=()):
    """A case with a statement D1 (a credit), a payslip D2 (the net pay) and an application D3, plus any more fields given as
    (document id, field) pairs."""
    more = lambda d: [f for doc, f in fields if doc == d]  # noqa: E731
    docs = [document("D1", "statement.pdf", fld("D1", "txn.credit", "52000.00", CREDIT, row=2), *more("D1")),
            document("D2", "payslip_03.pdf", fld("D2", "net_pay", "82000.00", NET), *more("D2")),
            document("D3", "application.pdf", *more("D3"))]
    return Case(id="C-test", created="2026-11-04T00:00:00Z", documents=docs, findings=list(findings))


def link(tmp_path, case, th=TH):
    cd = CaseDir.create(tmp_path)
    link_findings(case, Ctx(cd, AuditLog(cd.audit_path), th))
    return case


def net_pay_trio():
    """The spec's example: the net pay conflicts with the bank credit; its value is set in another font; a filled shape lies
    over it. The font and the shape are both visual."""
    net = fld("D2", "net_pay", "82000.00", NET)
    credit = fld("D1", "txn.credit", "52000.00", CREDIT, row=2)
    conflict = finding(1, "inconsistency", "cross_net_pay", "cross_document", field_evidence(net, "net pay in question"),
                       field_evidence(credit, "nearest credit"), title="Net pay not found among the credits", conf=0.95)
    font = finding(2, "observation", "pdf_fonts", "visual", at((102, 402, 258, 428), "set in another font", "82,000.00"),
                   title="Value set in a different font from the values beside it")
    shape = finding(3, "observation", "pdf_overlay", "visual", at((102, 402, 258, 428), "text drawn over the shape", "82,000.00"),
                    at((90, 395, 270, 435), "the filled shape"), title="Text written over a filled shape")
    return conflict, font, shape


def clusters(case):
    return [f for f in case.findings if f.fclass == "potential_manipulation"]


def related(case):
    return [f.related for f in case.findings]


# --- the grouping

def test_net_pay_cluster_is_potential_manipulation(tmp_path):
    case = link(tmp_path, built(*net_pay_trio()))
    members = case.findings[:3]
    (head,) = clusters(case)
    assert (head.id, head.detector, head.family, head.status, head.cluster) == ("F-004", "link", "cluster", "open", None)
    assert head.title == "Net pay on payslip_03.pdf: 3 findings from 2 kinds of check"
    assert [m.cluster for m in members] == ["F-004"] * 3
    assert [m.review_priority for m in members] == [2, 2, 2] and head.review_priority == 2  # the font and the shape are one family
    assert related(case)[:3] == [["F-002", "F-003"], ["F-001", "F-003"], ["F-001", "F-002"]]
    assert head.related == ["F-001", "F-002", "F-003"] and head.conf == 0.95  # the weakest reading it rests on
    assert [m.fclass for m in members] == ["inconsistency", "observation", "observation"]  # members keep their class
    assert head.detail == cluster_headline(members, case)


def test_the_cluster_cites_every_place_once_and_owns_its_evidence(tmp_path):
    case = link(tmp_path, built(*net_pay_trio()))
    members, (head,) = case.findings[:3], clusters(case)
    # the net pay field, the credit, the value that two members cite, and the shape: four places, not five citations
    assert [(e.doc, e.box) for e in head.evidence] == [("D2", NET), ("D1", CREDIT), ("D2", (102, 402, 258, 428)), ("D2", (90, 395, 270, 435))]
    assert head.evidence[0].field_id == "D2-net_pay" and head.evidence[0].note == "net pay in question"
    assert not {id(e) for e in head.evidence} & {id(e) for m in members for e in m.evidence}  # the crop stage sets crop_path on each


def test_priority_counts_distinct_families_not_findings(tmp_path):
    conflict, font, shape = net_pay_trio()
    total = finding(4, "inconsistency", "payslip_sums", "arithmetic", field_evidence(fld("D2", "net_pay", "82000.00", NET), "net pay in question"))
    case = link(tmp_path, built(conflict, font, shape, total))
    (head,) = clusters(case)
    assert head.id == "F-005" and head.review_priority == 3
    assert [f.review_priority for f in case.findings[:4]] == [3, 3, 3, 3]
    assert head.title == "Net pay on payslip_03.pdf: 4 findings from 3 kinds of check"


def test_unrelated_findings_not_merged(tmp_path):
    a = finding(1, "inconsistency", "payslip_sums", "arithmetic", at(NET, "net pay"))
    elsewhere = finding(2, "observation", "pdf_fonts", "visual", at((900, 1200, 1000, 1230)))  # same page, far away
    beside = finding(3, "observation", "pdf_overlay", "visual", at((250, 400, 420, 430)))  # touches the net pay box by a strip
    other_doc = finding(4, "observation", "pdf_meta", "metadata", at(NET, doc="D1"))  # the same numbers on another document
    case = link(tmp_path, built(a, elsewhere, beside, other_doc))
    assert clusters(case) == [] and len(case.findings) == 4
    assert [f.review_priority for f in case.findings] == [1, 1, 1, 1]
    assert related(case) == [[], [], [], []] and [f.cluster for f in case.findings] == [None] * 4


def test_same_family_same_box_counts_once(tmp_path):
    font = finding(1, "observation", "pdf_fonts", "visual", at(NET, "set in another font"))
    shape = finding(2, "observation", "pdf_overlay", "visual", at(NET, "under a shape"))
    case = link(tmp_path, built(font, shape))
    assert clusters(case) == [] and len(case.findings) == 2  # one family is not two
    assert [f.review_priority for f in case.findings] == [1, 1]
    assert related(case) == [["F-002"], ["F-001"]] and [f.cluster for f in case.findings] == [None, None]


def test_findings_that_cite_the_same_field_are_grouped_wherever_their_boxes_lie(tmp_path):
    net = fld("D2", "net_pay", "82000.00", NET)
    a = finding(1, "inconsistency", "payslip_sums", "arithmetic", field_evidence(net, "net pay in question"))
    b = finding(2, "inconsistency", "cross_net_pay", "cross_document", Evidence(doc="D2", page=1, box=(1, 1, 5, 5), field_id="D2-net_pay"))
    case = link(tmp_path, built(a, b))
    (head,) = clusters(case)
    assert head.related == ["F-001", "F-002"] and [f.cluster for f in case.findings[:2]] == [head.id, head.id]


@pytest.mark.parametrize("dy, joined", [(0, True), (500, False)])
def test_two_places_inside_one_field_are_grouped_through_the_field_and_not_through_each_other(tmp_path, dy, joined):
    left = finding(1, "observation", "pdf_fonts", "visual", at((102, 402 + dy, 150, 428 + dy)))  # the two boxes do not touch each other
    right = finding(2, "observation", "pdf_revisions", "metadata", at((200, 402 + dy, 258, 428 + dy)))
    case = link(tmp_path, built(left, right))
    assert (related(case)[0] == ["F-002"]) is joined and len(clusters(case)) == (1 if joined else 0)


def test_a_shape_over_a_field_is_grouped_with_the_finding_on_the_field(tmp_path):
    net = fld("D2", "net_pay", "82000.00", NET)
    a = finding(1, "inconsistency", "payslip_sums", "arithmetic", field_evidence(net, "net pay in question"))
    big = finding(2, "observation", "pdf_overlay", "visual", at((80, 380, 400, 450), "the filled shape"))  # holds the whole field
    assert len(clusters(link(tmp_path, built(a, big)))) == 1


@pytest.mark.parametrize("shift, limit, joined", [(40, 0.5, True), (50, 0.5, True), (60, 0.5, False), (40, 0.7, False)])
def test_boxes_join_when_the_overlap_reaches_the_threshold_share_of_the_smaller_box(tmp_path, shift, limit, joined):
    a = finding(1, "inconsistency", "payslip_sums", "arithmetic", at((0, 0, 100, 100)))
    b = finding(2, "observation", "pdf_fonts", "visual", at((shift, 0, shift + 100, 100)))  # 100 - shift of the width lies inside a
    case = link(tmp_path, built(a, b), th=Thresholds(link_overlap=limit))
    assert (related(case)[0] == ["F-002"]) is joined


def test_limitations_are_not_clustered(tmp_path):
    net = fld("D2", "net_pay", "82000.00", NET)
    conflict = finding(1, "inconsistency", "payslip_sums", "arithmetic", field_evidence(net, "net pay in question"))
    gap = limitation("cross_checks", "A comparison could not be made", "no credit was readable", [field_evidence(net, "net pay")])
    case = link(tmp_path, built(conflict, gap.model_copy(update={"id": "F-002"})))
    conflict, gap = case.findings
    assert clusters(case) == []  # a limitation is not a kind of check that fired
    assert (gap.cluster, gap.related, gap.review_priority, gap.fclass) == (None, [], 0, "processing_limitation")
    assert conflict.related == [] and conflict.review_priority == 1


def test_a_limitation_does_not_join_a_cluster_or_lend_it_evidence(tmp_path):
    gap = limitation("cross_checks", "A comparison could not be made", "x", [at((101, 401, 259, 429), "page")])
    case = link(tmp_path, built(*net_pay_trio(), gap.model_copy(update={"id": "F-004"})))
    (head,) = clusters(case)
    gap = case.findings[3]
    assert head.related == ["F-001", "F-002", "F-003"] and gap.cluster is None and gap.related == []
    assert all(e.note != "page" for e in head.evidence)


def test_whole_document_and_empty_evidence_links_nothing(tmp_path):
    a = finding(1, "observation", "pdf_meta", "metadata", doc_evidence("D2", "file record"))
    b = finding(2, "observation", "pdf_fonts", "visual", doc_evidence("D2", "page content"))
    c = finding(3, "inconsistency", "payslip_sums", "arithmetic", at((5, 5, 5, 5)))  # a point has no area
    d = finding(4, "observation", "pdf_overlay", "visual", at((5, 5, 5, 5)))
    case = link(tmp_path, built(a, b, c, d))
    assert clusters(case) == [] and related(case) == [[], [], [], []]


# --- entities: the same name, address, employer or account in two documents

@pytest.mark.parametrize("role_a, value_a, role_b, value_b, joined", [
    ("name", "Meera K. Varghese", "name", "VARGHESE, meera k", True),
    ("address", "Flat 4, Rose Court, Mill Road", "address", "flat 4 rose court mill road", True),
    ("employer", "Harborview Industries Pvt Ltd", "employer", "Harborview Industries Pvt Ltd", True),
    ("account", "TST-1234567890", "account", "tst 1234567890", True),
    ("account", "TST-1234567890", "account", "TST-1234567899", False),  # not the same value
    ("name", "Harborview Industries", "employer", "Harborview Industries", False),  # the same words, not the same kind of thing
    ("", "52000.00", "", "52000.00", False),  # an amount is not an entity
    ("other", "Meera K. Varghese", "other", "Meera K. Varghese", False),  # only the four entity roles join
    ("name", None, "name", None, False),  # nothing was read
])
def test_entity_join_only_through_entity_fields(tmp_path, role_a, value_a, role_b, value_b, joined):
    box_a, box_b = (100.0, 700.0, 300.0, 730.0), (100.0, 1500.0, 300.0, 1530.0)
    a = finding(1, "observation", "pdf_fonts", "visual", at(box_a, doc="D1"))  # no field id: the field is found by its place
    b = finding(2, "observation", "pdf_meta", "metadata", at(box_b, doc="D3"))
    case = built(a, b, fields=[("D1", fld("D1", "f_a", value_a, box_a, role=role_a)), ("D3", fld("D3", "f_b", value_b, box_b, role=role_b))])
    link(tmp_path, case)
    assert (related(case)[0] == ["F-002"]) is joined
    assert len(clusters(case)) == (1 if joined else 0)  # two families, so a joined pair is a cluster


def test_a_finding_that_cites_an_entity_field_by_id_joins_by_its_value(tmp_path):
    holder = fld("D1", "account_holder", "Meera K. Varghese", (100, 700, 300, 730), role="name")
    applicant = fld("D3", "applicant_name", "meera k varghese", (100, 1500, 300, 1530), role="name")
    a = finding(1, "inconsistency", "cross_name", "cross_document", field_evidence(holder, "holder"))
    b = finding(2, "observation", "pdf_fonts", "visual", field_evidence(applicant, "applicant"))
    case = link(tmp_path, built(a, b, fields=[("D1", holder), ("D3", applicant)]))
    (head,) = clusters(case)
    assert head.related == ["F-001", "F-002"]


# --- context rules are rules of thumb, not a kind of check

def test_a_context_rule_is_linked_but_does_not_count_as_a_kind_of_check(tmp_path):
    net = fld("D2", "net_pay", "82000.00", NET)

    def three():
        rule = finding(1, "observation", "context_emi", "cross_document", field_evidence(net, "net pay"), title="Context rule: EMI is high")
        font = finding(2, "observation", "pdf_fonts", "visual", at(NET, "set in another font"))
        total = finding(3, "inconsistency", "payslip_sums", "arithmetic", field_evidence(net, "net pay in question"))
        return rule, font, total

    rule, font, total = three()
    case = link(tmp_path / "a", built(rule, font))
    assert clusters(case) == []  # a rule of thumb and one real check are still one kind of check
    assert related(case) == [["F-002"], ["F-001"]] and [f.review_priority for f in case.findings] == [1, 1]

    case = link(tmp_path / "b", built(*three()))
    (head,) = clusters(case)
    assert head.related == ["F-001", "F-002", "F-003"] and head.review_priority == 2  # visual and arithmetic: the rule adds nothing

    case = link(tmp_path / "c", built(three()[0]))
    assert case.findings[0].review_priority == 0  # alone, no check fired at all


# --- the headline

def test_headline_is_the_spec_form_with_the_conflict_first():
    case = built(*net_pay_trio())
    conflict, font, shape = case.findings
    expected = ("Net pay on payslip_03.pdf: Net pay not found among the credits (cross-document inconsistency); "
                "Value set in a different font from the values beside it (visual observation); "
                "Text written over a filled shape (visual observation).")
    assert cluster_headline([conflict, font, shape], case) == expected
    assert cluster_headline([shape, font, conflict], case) == expected  # the order given does not matter


def test_the_headline_names_a_table_cell_by_its_column_and_row():
    credit = fld("D1", "txn.credit", "52000.00", CREDIT, row=2)
    a = finding(1, "inconsistency", "cross_net_pay", "cross_document", field_evidence(credit, "credit"), title="T")
    b = finding(2, "observation", "pdf_fonts", "visual", at(CREDIT, doc="D1"), title="U")
    assert cluster_headline([b, a], built(a, b)).startswith("Credit in row 2 on statement.pdf: T (cross-document inconsistency); U")


def test_the_headline_place_is_the_field_most_findings_cite_and_a_finding_counts_once():
    credit = fld("D1", "txn.credit", "52000.00", CREDIT, row=2)
    a = finding(1, "inconsistency", "cross_net_pay", "cross_document", field_evidence(credit, "credit"), title="A")
    b = finding(2, "observation", "pdf_overlay", "visual", at(NET, "text"), at((90, 395, 270, 435), "shape"), title="B")  # the net pay twice
    c = finding(3, "observation", "pdf_fonts", "visual", at(NET, "font"), title="C")
    case = built(a, b, c)
    assert cluster_headline([a, b], case).startswith("Credit in row 2 on statement.pdf: A")  # one finding each, so the first wins
    assert cluster_headline([a, b, c], case).startswith("Net pay on payslip_03.pdf: A")  # two findings against one


def test_the_headline_says_the_page_where_no_field_lies_and_the_documents_where_nothing_is_placed():
    a = finding(1, "observation", "pdf_fonts", "visual", at((900, 1200, 1000, 1230)), title="T")  # no field lies here
    assert cluster_headline([a], built(a)).startswith("Page 1 of payslip_03.pdf: T (visual observation)")
    c = finding(2, "observation", "pdf_meta", "metadata", doc_evidence("D1", "file record"))
    d = finding(3, "observation", "pdf_fonts", "visual", doc_evidence("D3", "page content"))
    assert cluster_headline([c, d], built(c, d)).startswith("statement.pdf and application.pdf: ")


def test_a_long_cluster_lists_six_members_and_counts_the_rest():
    members = [finding(n, "observation", "pdf_fonts", "visual", at(NET), title=f"Title {n}") for n in range(1, 10)]
    text = cluster_headline(members, built(*members))
    assert text.count("(visual observation)") == 6 and text.endswith("; and 3 more.") and "Title 6" in text and "Title 7" not in text


def test_a_filename_cannot_carry_control_characters_into_the_headline():
    case = built(*net_pay_trio())
    case.documents[1].filename = "pay\x1b[31m\nslip.pdf"
    text = cluster_headline(case.findings, case)
    assert "\x1b" not in text and "\n" not in text and "slip.pdf" in text


# --- all or nothing, and the trail

def test_a_failure_while_linking_leaves_no_half_linked_case(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(linking, "cluster_headline", boom)
    case = built(*net_pay_trio())
    before = case.model_dump()
    with pytest.raises(RuntimeError):
        link(tmp_path, case)
    assert case.model_dump() == before  # no member points at a cluster that was never created


def test_the_link_stage_is_audited(tmp_path):
    case = built(*net_pay_trio())
    cd = CaseDir.create(tmp_path)
    audit = AuditLog(cd.audit_path)
    link_findings(case, Ctx(cd, audit, TH))
    (done,) = [e.data for e in audit.events() if e.event == "findings_linked"]
    assert done == {"findings": 3, "linked": 3, "clusters": 1}


# --- real runs: a drawn edit goes through the whole pipeline

def run(tmp_path, *pdfs):
    case, cd, _ = create_case(tmp_path / "data", [(f"d{i}.pdf", p) for i, p in enumerate(pdfs, 1)], TH)
    return run_case(cd, TH)


@pytest.fixture(scope="module")
def net_pay_run(tmp_path_factory):
    """The net pay on the payslip changed in a later save of the file; the statement and the application are genuine."""
    ident = identity(2)
    pdf, m = d1_incremental_edit(draw_payslip(ident, seed=2).pdf, money(ident.net_pay), money(ident.net_pay + 20_000))
    return run(tmp_path_factory.mktemp("net_pay"), draw_statement(ident, seed=2).pdf, pdf, draw_application(ident, seed=2).pdf), m


def test_an_edited_net_pay_forms_one_cluster_in_a_real_run(net_pay_run):
    case, m = net_pay_run
    (head,) = clusters(case)
    members = [f for f in case.findings if f.cluster == head.id]
    assert sorted(f.detector for f in members) == ["cross_net_pay", "payslip_sums", "payslip_words", "pdf_revisions"]
    assert {f.family for f in members} == {"metadata", "arithmetic", "cross_document"} and head.review_priority == 3
    assert head.related == sorted(f.id for f in members) and all(f.review_priority == 3 for f in members)
    assert any(e.doc == "D2" and e.page == m.page and iou(e.box, m.box) >= 0.5 for e in head.evidence)  # it points at the edit
    assert head.detail.startswith("Net pay on d2.pdf: ") and head.explanation_source == "template"
    assert "not a probability" in head.explanation  # explain runs after link and says what a cluster is not


def test_pipeline_never_sets_reviewer_statuses(net_pay_run):
    case, _ = net_pay_run
    assert len(case.findings) == 5 and {f.status for f in case.findings} == {"open"}  # the four findings and the cluster's


def test_every_crop_belongs_to_the_finding_that_cites_it(net_pay_run):
    case, _ = net_pay_run
    crops = [e.crop_path for f in case.findings for e in f.evidence if e.crop_path]
    assert crops
    for f in case.findings:  # an evidence object shared with the cluster would carry the cluster's crop
        for e in f.evidence:
            assert e.crop_path is None or Path(e.crop_path).name.startswith(f"{f.id}-")


def test_an_edited_credit_forms_one_cluster_through_the_cell_it_shares(tmp_path):
    ident = identity(1)
    stmt = draw_statement(ident, seed=1)
    credit = next(r["credit"] for r in stmt.truth["rows"] if r["credit"])
    pdf, m = d1_incremental_edit(stmt.pdf, money(credit), "9,99,999.00")
    case = run(tmp_path, pdf, draw_payslip(ident, seed=1).pdf, draw_application(ident, seed=1).pdf)
    (head,) = clusters(case)
    members = [f for f in case.findings if f.cluster == head.id]
    # the revision observation names the cell by its box only; the other two cite the field that sits there
    assert sorted(f.detector for f in members) == ["cross_net_pay", "pdf_revisions", "statement_balance"]
    assert head.review_priority == 3 and head.detail.startswith("Credit in row 2 on d1.pdf: ")  # the cell all three meet at, not the balance one of them cites first
    assert any(e.doc == "D1" and e.page == m.page and iou(e.box, m.box) >= 0.5 for e in head.evidence)
