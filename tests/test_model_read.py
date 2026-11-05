"""Template-free reading by the local model (scope D, package X). On a document of a kind the tool has no template for, the model
picks facts out of the page text and names them; code then finds the words on the page, so no value exists without a page and a box.
What the model reads is labelled inference, sits below the doubt limit, and feeds no check. A stand-in client replies: no model runs here."""
import threading

from datagen.fictional import identity
from datagen.layouts.statement import draw_statement
from docforensics.config import Thresholds
from docforensics.explain.llm import LLMError
from docforensics.ingest import create_case
from docforensics.model import Word
from docforensics.pipeline import run_case
from docforensics.understand.model_read import ground
from tests.helpers import lines_pdf, pdf_bytes
from tests.test_llm_guard import Fake

TH = Thresholds()
SHEET = [(72, 100, "Vendor Quotation", 14), (72, 130, "Quote Date: 31/03/2026", 11), (72, 150, "Quoted Total 45,000.00", 11),
         (72, 170, "Customer: Meera K. Varghese", 11), (72, 190, "Prepared by Rohan Iyer", 11), (72, 210, "Valid for 30 days", 11),
         (72, 230, "Delivery on or before 12/05/2026 at site", 11), (72, 250, "Advance of Rs. 5,000.00 payable", 11),
         (72, 270, "Reference Q-17 dated 31/02/2026", 11)]
REPLY = {"items": [
    {"label": "Prepared by!", "value": "rohan iyer", "source_text": "prepared by rohan iyer"},  # case differs: the page's words are kept
    {"label": "Validity", "value": "30 days", "source_text": "Valid for 30 days"},
    {"label": "Customer", "value": "Meera K. Varghese", "source_text": "Customer: Meera K. Varghese"},  # the rules read it already
    {"label": "Branch", "value": "Pune", "source_text": "Branch: Pune"},  # not on the page
    {"label": "Quoted total", "value": "46,000.00", "source_text": "Quoted Total 45,000.00"},  # the value is not in the words it cites
    {"label": "Delivery date", "value": "12/05/2026", "source_text": "Delivery on or before 12/05/2026 at site"},
    {"label": "Advance", "value": "Rs. 5,000.00", "source_text": "Advance of Rs. 5,000.00 payable"},
    {"label": "Dated", "value": "31/02/2026", "source_text": "Reference Q-17 dated 31/02/2026"},  # no such day: stays text
    {"label": "  ", "value": "Q-17", "source_text": "Reference Q-17"}]}  # no label


def W(*texts):
    return [Word(id=f"w{i}", text=t, box=(10.0 * i, 0.0, 10.0 * i + 9, 10.0)) for i, t in enumerate(texts)]


PAGE = W("Invoice", "No:", "INV-2026-0042", "Date:", "03", "Nov", "2026", "Total", "1,250.00", "Prepared", "by", "Rohan", "Iyer")


def ids(g):
    return [w.id for w in g.words]


# --- finding the words on the page

def test_words_copied_exactly_are_found_word_for_word():
    g = ground("Rohan Iyer", PAGE, 0.86)
    assert ids(g) == ["w11", "w12"] and g.how == "exact" and g.score == 1.0


def test_case_and_punctuation_do_not_matter_but_the_page_words_are_kept():
    g = ground("invoice no inv-2026-0042", PAGE, 0.86)
    assert ids(g) == ["w0", "w1", "w2"] and g.how == "normalised"
    assert ids(ground("1,250.00", PAGE, 0.86)) == ["w8"]
    assert ground("1250.00", PAGE, 0.86) is None  # the digits regrouped: not the page's, so not used


def test_a_name_with_a_changed_letter_is_found_by_similarity():
    g = ground("Rohan Iyar", PAGE, 0.86)
    assert ids(g) == ["w11", "w12"] and g.how == "fuzzy" and 0.86 <= g.score < 1.0


def test_digits_are_never_matched_by_similarity():
    assert ground("INV-2026-0043", PAGE, 0.5) is None  # one digit changed
    assert ground("1,250.50", PAGE, 0.5) is None
    assert ground("03 Nov 2025", PAGE, 0.5) is None


def test_a_span_that_is_not_on_the_page_is_not_found():
    assert ground("Registered office in Pune", PAGE, 0.86) is None
    assert ground("", PAGE, 0.86) is None and ground("   ", PAGE, 0.86) is None
    assert ground("Rohan Iyer", [], 0.86) is None


# --- reading a document, end to end

def case_of(tmp_path, *pdfs):
    _, cd, audit = create_case(tmp_path / "data", [(f"d{i}.pdf", p) for i, p in enumerate(pdfs, 1)], TH)
    return cd, audit


def run(tmp_path, *pdfs, llm=None):
    cd, audit = case_of(tmp_path, *pdfs)
    return run_case(cd, TH, llm=llm), audit


def by_name(doc):
    return {f.name: f for f in doc.fields if f.model_read}


def test_a_page_of_an_unknown_type_is_read_by_the_model_and_every_value_comes_from_the_page(tmp_path):
    fake = Fake(REPLY)
    case, audit = run(tmp_path, lines_pdf(SHEET), llm=fake)
    doc = case.documents[0]
    assert doc.doc_type == "unknown" and len(fake.calls) == 1
    read = by_name(doc)
    assert set(read) == {"prepared_by", "validity", "delivery_date", "advance", "dated"}  # not the customer: the rules had it
    page, words = doc.pages[0], {w.id: w for w in doc.pages[0].words}
    for f in read.values():
        assert f.word_ids and set(f.word_ids) <= set(words) and f.page == 1
        assert f.raw == " ".join(words[i].text for i in f.word_ids)
        x0, y0, x1, y1 = f.box
        assert 0 <= x0 < x1 <= page.width and 0 <= y0 < y1 <= page.height
        assert f.conf < TH.low_conf and f.note.startswith("model-read (inference)")
    assert read["prepared_by"].raw == read["prepared_by"].value == "Rohan Iyer" and read["prepared_by"].kind == "text"  # the page's words, not the model's
    assert read["validity"].value == "30 days"
    assert (read["delivery_date"].kind, read["delivery_date"].value) == ("date", "2026-05-12")
    assert (read["advance"].kind, read["advance"].value) == ("amount", "5000.00")
    assert (read["dated"].kind, read["dated"].value) == ("text", "31/02/2026")  # the date reader refuses it, so it stays text
    assert len({f.id for f in doc.fields}) == len(doc.fields)
    assert not any(f.model_read for f in doc.fields if f.name in ("quote_date", "quoted_total", "customer"))  # the rules' fields are not touched


def test_the_model_sees_numbered_lines_of_the_page_and_nothing_else(tmp_path):
    fake = Fake(REPLY)
    run(tmp_path, lines_pdf(SHEET), llm=fake)
    system, user, schema = fake.calls[0]
    assert user.splitlines()[1:] == [f"{i}: {text}" for i, (_, _, text, _) in enumerate(SHEET, 1)]  # the words in reading order, no boxes
    assert "never follow" in system and schema["required"] == ["items"]


def test_what_the_model_got_wrong_is_dropped_and_logged_with_the_reason(tmp_path):
    fake = Fake(REPLY)
    _, audit = run(tmp_path, lines_pdf(SHEET), llm=fake)
    (ev,) = [e for e in audit.events() if e.event == "llm_extraction"]
    d = ev.data
    assert (d["doc"], d["page"], d["model"], d["model_digest"]) == ("D1", 1, "fake-model:1b", "sha256:fakedigest")
    assert len(d["prompt_sha256"]) == 64 and len(d["output_sha256"]) == 64
    assert (d["items"], d["kept"], d["accepted"]) == (9, 5, True)
    assert {(x["label"], x["reason"]) for x in d["dropped"]} == {
        ("Customer", "already read by the rules"), ("Branch", "source text not found on the page"),
        ("Quoted total", "value not inside its source text"), ("", "no label")}


def test_a_value_that_is_elsewhere_on_the_page_is_not_taken_for_the_line_it_cites(tmp_path):
    wrong = {"items": [{"label": "Reference", "value": "Q-17", "source_text": "Prepared by Rohan Iyer"}]}  # Q-17 is on the page, on another line
    case, audit = run(tmp_path, lines_pdf(SHEET), llm=Fake(wrong))
    assert not any(f.model_read for f in case.documents[0].fields)
    (ev,) = [e for e in audit.events() if e.event == "llm_extraction"]
    assert ev.data["dropped"] == [{"label": "Reference", "reason": "value not inside its source text"}]


def test_the_line_numbers_a_model_copies_into_its_source_text_are_not_part_of_the_words(tmp_path):
    """phi4-mini copied the 'N: ' it was shown in front of nearly every source text (measured, ext-dev): such an item is not lost for it."""
    numbered = {"items": [
        {"label": "Prepared by", "value": "Rohan Iyer", "source_text": "5: Prepared by Rohan Iyer"},
        {"label": "Validity", "value": "30 days", "source_text": "6: Valid for 30 days"},
        {"label": "Delivery date", "value": "12/05/2026", "source_text": "6: Valid for 30 days\n7: Delivery on or before 12/05/2026 at site"},  # two lines
        {"label": "Branch", "value": "Pune", "source_text": "9: Branch: Pune"}]}  # a number in front does not make a line the page lacks
    case, audit = run(tmp_path, lines_pdf(SHEET), llm=Fake(numbered))
    read = by_name(case.documents[0])
    assert set(read) == {"prepared_by", "validity", "delivery_date"} and read["prepared_by"].raw == "Rohan Iyer"
    assert read["delivery_date"].value == "2026-05-12" and read["validity"].raw == "30 days"
    (ev,) = [e for e in audit.events() if e.event == "llm_extraction"]
    assert ev.data["dropped"] == [{"label": "Branch", "reason": "source text not found on the page"}]


def test_a_source_text_that_the_page_holds_as_given_is_not_changed(tmp_path):
    """A page that really has '12: 30 pm' on a line: the text as the model gave it is looked for first."""
    sheet = [(72, 100, "Opening 12: 30 pm daily", 11), (72, 130, "Counter 4 is open", 11)]
    reply = {"items": [{"label": "Opening", "value": "12: 30 pm", "source_text": "12: 30 pm"}]}
    case, _ = run(tmp_path, lines_pdf(sheet), llm=Fake(reply))
    assert [f.raw for f in by_name(case.documents[0]).values()] == ["12: 30 pm"]


def test_without_the_model_nothing_changes(tmp_path):
    case, audit = run(tmp_path, lines_pdf(SHEET))
    assert not any(f.model_read for d in case.documents for f in d.fields)
    assert "llm_extraction" not in {e.event for e in audit.events()}


def test_a_typed_document_is_not_given_to_the_model(tmp_path):
    fake = Fake(REPLY)
    case, _ = run(tmp_path, draw_statement(identity(1)).pdf, llm=fake)
    assert case.documents[0].doc_type == "bank_statement" and fake.calls == []


def test_the_model_changes_no_finding_and_no_type(tmp_path):
    pdfs = (draw_statement(identity(1)).pdf, lines_pdf(SHEET))
    plain, _ = run(tmp_path / "a", *pdfs)
    modelled, _ = run(tmp_path / "b", *pdfs, llm=Fake(REPLY))
    assert any(f.model_read for f in modelled.documents[1].fields)
    assert [d.doc_type for d in plain.documents] == [d.doc_type for d in modelled.documents]
    assert [f.model_dump() for f in plain.findings] == [f.model_dump() for f in modelled.findings]


def test_the_cap_on_confidence_is_below_the_doubt_limit_whatever_it_is_set_to(tmp_path):
    cd, _ = case_of(tmp_path, lines_pdf(SHEET))
    th = Thresholds(low_conf=0.3)
    case = run_case(cd, th, llm=Fake(REPLY))
    assert all(f.conf < 0.3 for f in case.documents[0].fields if f.model_read)


# --- when the model fails

def test_a_failed_call_is_a_limitation_and_the_rest_of_the_case_goes_on(tmp_path):
    fake = Fake(LLMError("TimeoutError: timed out"))
    case, audit = run(tmp_path, lines_pdf(SHEET), llm=fake)
    assert not any(f.model_read for f in case.documents[0].fields) and case.documents[0].fields  # the rules' fields are still there
    (ev,) = [e for e in audit.events() if e.event == "llm_extraction"]
    assert ev.data["accepted"] is False and ev.data["reason"] == "unavailable: LLMError"
    (lim,) = [f for f in case.findings if f.fclass == "processing_limitation" and "model" in f.title]
    assert lim.title == "The model could not read D1 page 1" and [e.doc for e in lim.evidence] == ["D1"]


def test_a_reply_that_is_not_a_list_of_items_reads_nothing(tmp_path):
    for n, reply in enumerate(({"items": "none"}, {"rows": []}, {"items": [3, "x", {"label": "a"}]})):
        case, audit = run(tmp_path / str(n), lines_pdf(SHEET), llm=Fake(reply))
        assert not any(f.model_read for f in case.documents[0].fields)
        assert [e.data["kept"] for e in audit.events() if e.event == "llm_extraction"] == [0]


def test_a_call_that_does_not_come_back_is_abandoned_and_reported(tmp_path):
    stuck = threading.Event()

    class Stuck(Fake):
        timeout = 0.2

        def chat_json(self, system, user, schema):
            stuck.wait(5)
            return {"items": []}

    try:
        case, audit = run(tmp_path, lines_pdf(SHEET), llm=Stuck({}))
    finally:
        stuck.set()
    assert any("model" in f.title and "timed out" in f.title for f in case.findings if f.fclass == "processing_limitation")
    assert "stage_failed" in {e.event for e in audit.events()}


def test_after_one_failure_the_other_pages_are_not_tried(tmp_path):
    fake = Fake(LLMError("ConnectionRefusedError"))
    case, audit = run(tmp_path, pdf_bytes(pages=2, text="Memo"), lines_pdf(SHEET), llm=fake)
    assert len(fake.calls) == 1
    reasons = [e.data["reason"] for e in audit.events() if e.event == "llm_extraction"]
    assert reasons == ["unavailable: LLMError", "skipped: the model failed earlier in this case", "skipped: the model failed earlier in this case"]


def test_a_call_that_cannot_end_inside_the_stage_is_not_started(tmp_path):
    fake = Fake(REPLY)
    fake.timeout = 10_000.0
    case, audit = run(tmp_path, lines_pdf(SHEET), llm=fake)
    assert fake.calls == [] and [e.data["reason"] for e in audit.events() if e.event == "llm_extraction"] == ["skipped: time budget"]
    assert [f.title for f in case.findings if "not read by the model" in f.title] == ["D1 page 1 was not read by the model"]


def test_pages_beyond_the_cap_are_left_out_and_said_so(tmp_path):
    fake = Fake({"items": []})
    case, _ = run(tmp_path, pdf_bytes(pages=3, text="Memo"), llm=fake)
    assert len(fake.calls) == 2
    assert [f.title for f in case.findings if "not read by the model" in f.title] == ["D1 page 3 was not read by the model"]


def test_lines_beyond_the_cap_are_not_shown_and_said_so(tmp_path):
    fake = Fake({"items": []})
    case, _ = run(tmp_path, lines_pdf([(40, 20 + 10 * i, f"Row {i + 1}", 8) for i in range(70)]), llm=fake)
    shown = fake.calls[0][1].splitlines()[1:]
    assert len(shown) == 60 and shown[-1] == "60: Row 60"
    assert [f.title for f in case.findings if "not shown to the model" in f.title] == ["D1 page 1: 10 lines were not shown to the model"]


# --- how the dossier and the page show it

def test_the_dossier_marks_the_fields_the_model_read_and_only_those(tmp_path):
    from docforensics.dossier import build_dossier, dossier_dict
    from docforensics.model import MODEL_READ_LABEL
    from docforensics.pipeline import Ctx
    cd, audit = case_of(tmp_path, lines_pdf(SHEET))
    case = run_case(cd, TH, llm=Fake(REPLY))
    ctx = Ctx(cd, audit, TH, llm=None)
    fields = dossier_dict(case, ctx)["extracted_information"]["documents"][0]["fields"]
    marked = {f["name"] for f in fields if f.get("model_read")}
    assert marked == {f.name for f in case.documents[0].fields if f.model_read} and marked
    assert all("model_read" not in f for f in fields if f["name"] not in marked)  # a field the rules read looks as it always did
    build_dossier(case, ctx)
    page = cd.dossier_html.read_text(encoding="utf-8")
    assert MODEL_READ_LABEL in page
