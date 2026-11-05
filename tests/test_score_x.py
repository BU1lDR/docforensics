"""The scorer of package X (scope D): what the local model read from a page of a type the tool has no spec for, against what the generator
printed. The counting rules are in the scorer's docstring and are fixed before any model is run on the pack. A stand-in client replies."""
import copy

from datagen.unseen import build_case, plan_cases
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from evaluation.score_x import format_report, score_case, summarise
from tests.test_llm_guard import Fake

TH = Thresholds()


class Router(Fake):
    """Replies by document: one reply for the invoice's page and one for the bill's."""

    def chat_json(self, system, user, schema):
        self.calls.append((system, user, schema))
        return copy.deepcopy(self.reply["invoice" if "INV-" in user else "bill"])


def item(label, text):
    return {"label": label, "value": text, "source_text": text}


def test_each_field_is_right_misnamed_partial_read_by_the_rules_or_missing(tmp_path):
    files, entry = build_case(plan_cases("ext-dev", 4)[0])
    inv, bill = (d["fields"] for d in entry["docs"])
    reply = {"invoice": {"items": [
        item("Invoice number", inv["invoice_number"]["text"]),  # right
        item("Seller", inv["seller"]["text"]),  # right
        item("Bank account", inv["payment_terms"]["text"]),  # at the terms' words, named as the account: misnamed
        item("Bill to", inv["buyer"]["text"].split()[0]),  # one word of three: partial
        item("Bank", "XYZ-000"),  # not on the page: dropped
        item("Document title", "Tax Invoice"),  # a fact nobody listed
        item("First item", entry["docs"][0]["rows"][0]["description"]["text"])]},  # a table cell
        "bill": {"items": [item("Consumer number", bill["consumer_no"]["text"])]}}
    _, cd, audit = create_case(tmp_path / "data", [(n, d) for n, d in files.items()], TH)
    case = run_case(cd, TH, llm=Router(reply))
    res = score_case(entry, case, [e.data for e in audit.events() if e.event == "llm_extraction"], [41.5, 12.0])
    out = {(r["type"], r["field"]): r for r in res["fields"]}
    assert len(out) == len(inv) + len(bill) and {r["case"] for r in out.values()} == {"ext-dev-x-0000"}
    assert [out[("invoice", f)]["outcome"] for f in ("invoice_number", "seller", "payment_terms", "buyer")] == ["right", "right", "misnamed", "partial"]
    assert out[("invoice", "invoice_number")]["exact"] is True and out[("invoice", "invoice_number")]["got"] == "invoice_number"
    assert out[("invoice", "payment_terms")]["got"] == "bank_account" and out[("invoice", "payment_terms")]["exact"] is True
    assert out[("bill", "consumer_no")]["outcome"] == "right" and out[("bill", "bill_number")]["outcome"] == "missing"
    assert {r["outcome"] for r in out.values()} <= {"right", "misnamed", "partial", "rules", "missing"}
    assert any(r["outcome"] == "rules" for r in out.values())  # the rules' own reading of 'Label  date' and 'Label  amount' lines
    assert sorted(x["where"] for x in res["extras"]) == ["table cell", "unlisted"]
    assert res["calls"]["items"] == 8 and res["calls"]["kept"] == 7 and [d["reason"] for d in res["dropped"]] == ["source text not found on the page"]
    assert res["seconds"] == [41.5, 12.0]


def test_the_summary_counts_by_outcome_kind_and_medium_and_the_report_states_the_rules(tmp_path):
    files, entry = build_case(plan_cases("ext-dev", 4)[0])
    inv = entry["docs"][0]["fields"]
    reply = {"invoice": {"items": [item("Invoice number", inv["invoice_number"]["text"])]}, "bill": {"items": []}}
    _, cd, audit = create_case(tmp_path / "data", [(n, d) for n, d in files.items()], TH)
    case = run_case(cd, TH, llm=Router(reply))
    res = score_case(entry, case, [e.data for e in audit.events() if e.event == "llm_extraction"], [30.0, 20.0])
    s = summarise([res])
    total = sum(s["outcomes"].values())
    assert total == len(res["fields"]) and s["outcomes"]["right"] == 1
    assert s["by_kind"]["id"]["right"] == 1 and sum(sum(c.values()) for c in s["by_kind"].values()) == total
    assert set(s["by_medium"]) == {"digital"} and s["seconds"] == {"calls": 2, "mean": 25.0, "median": 25.0, "max": 30.0}
    text = format_report({**s, "run": {"model": "fake-model:1b", "split": "ext-dev", "cases": 1}})
    assert "IoU" in text and "right" in text and "fake-model:1b" in text and "inference" in text


def test_a_failed_call_is_counted_as_a_page_not_read(tmp_path):
    files, entry = build_case(plan_cases("ext-dev", 4)[0])
    _, cd, audit = create_case(tmp_path / "data", [(n, d) for n, d in files.items()], TH)
    from docforensics.explain.llm import LLMError
    case = run_case(cd, TH, llm=Fake(LLMError("TimeoutError")))
    res = score_case(entry, case, [e.data for e in audit.events() if e.event == "llm_extraction"], [])
    assert res["calls"]["accepted"] == 0 and res["calls"]["pages"] == 2
    assert not any(r["outcome"] == "right" for r in res["fields"])


# --- the runner: record the replies, then score them again without the model

class FirstLine(Fake):
    """Reads the first line of whatever page it is shown as the seller (an invoice's first line is its seller's name)."""

    def chat_json(self, system, user, schema):
        self.calls.append((system, user, schema))
        first = user.splitlines()[1].split(": ", 1)[1]
        return {"items": [{"label": "Seller", "value": first, "source_text": first}]}


def test_a_run_is_recorded_and_the_same_scores_come_back_from_the_saved_replies_without_the_model(tmp_path):
    import json

    from evaluation.run_x import run
    live = run("ext-dev", 2, 0, tmp_path / "live", client=FirstLine({}))
    saved = tmp_path / "live" / "ext-dev-fake-model-1b.json"
    assert saved.exists() and (tmp_path / "live" / "ext-dev-fake-model-1b.md").exists()
    assert live["outcomes"]["right"] == 2 and live["cases"] == 2 and live["seconds"]["calls"] == 4  # two invoices' sellers; four pages read
    again = run("ext-dev", 2, 0, tmp_path / "again", replay=saved)
    assert again["outcomes"] == live["outcomes"] and again["extras"] == live["extras"] and again["seconds"] == live["seconds"]
    assert json.loads(saved.read_text(encoding="utf-8"))["run"]["model"] == "fake-model:1b"


def test_a_replay_that_is_asked_what_it_never_saw_reads_nothing(tmp_path):
    from evaluation.run_x import run
    run("ext-dev", 1, 0, tmp_path / "live", client=FirstLine({}))
    other = run("ext-dev", 1, 1, tmp_path / "again", replay=tmp_path / "live" / "ext-dev-fake-model-1b.json")  # another case: other prompts
    assert other["calls"]["accepted"] == 0 and other["outcomes"]["right"] == 0


def test_a_case_that_did_not_finish_counts_every_fact_as_missing():
    _, entry = build_case(plan_cases("ext-dev", 4)[1])
    res = score_case(entry, None, [], [])
    assert res["fields"] and {r["outcome"] for r in res["fields"]} == {"missing"} and res["calls"]["pages"] == 0
