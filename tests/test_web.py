"""The review app (design 7.8): upload, a background run, pages and crops served by validated name, reviewer actions in the audit trail,
nothing from a document reaching the page as markup, and nothing listening but the loopback address."""
import hashlib
import re
import shutil
import threading
import time

import pytest
from fastapi.testclient import TestClient

from docforensics import cli
from docforensics.audit import AuditLog
from docforensics.capabilities import load_capabilities
from docforensics.config import Thresholds
from docforensics.dossier import CLASS_LABEL, READING_LABEL, SOURCE_LABEL
from docforensics.ingest import create_case
from docforensics.model import Reasoning, Relation
from docforensics.store import CASE_ID_RE, CaseDir, load_case, save_case
from docforensics.web import app as web
from docforensics.web.app import HOST, STATIC, create_app
from tests.helpers import d1_edited_statement, pdf_bytes

BASE = "http://127.0.0.1:8000"
ABSENT = "C-20260101-000000-abcd"
VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)


def make_client(data, th=None):
    return TestClient(create_app(data, th), base_url=BASE)


def upload(client, *files):
    r = client.post("/api/cases", files=[("files", (name, data, "application/octet-stream")) for name, data in files])
    assert r.status_code == 200, r.text
    return r.json()["case_id"]


def wait_done(client, cid, seconds=60):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        r = client.get(f"/api/cases/{cid}")
        assert r.status_code == 200, r.text
        if r.json()["status"] != "processing":
            return r.json()
        time.sleep(0.1)
    pytest.fail(f"case {cid} was still processing after {seconds} s")


def events_of(client, cid, name):
    return [e for e in client.get(f"/api/cases/{cid}/audit").json()["events"] if e["event"] == name]


@pytest.fixture(scope="module")
def shared(tmp_path_factory):
    """One real run: an edited statement and a plain PDF, analysed by the app."""
    data = tmp_path_factory.mktemp("web") / "data"
    client = make_client(data)
    cid = upload(client, ("statement.pdf", d1_edited_statement()), ("note.pdf", pdf_bytes()))
    assert wait_done(client, cid)["status"] == "done"
    return data, cid


@pytest.fixture
def case(shared, tmp_path):
    """A private copy of the shared run with its own app, so a test may change it."""
    src, cid = shared
    data = tmp_path / "data"
    shutil.copytree(src, data)
    return make_client(data), cid, data


def test_upload_two_files_completes(tmp_path):
    client = make_client(tmp_path / "data")
    cid = upload(client, ("statement.pdf", d1_edited_statement()), ("note.pdf", pdf_bytes()))
    assert CASE_ID_RE.fullmatch(cid)
    out = wait_done(client, cid)
    assert out["status"] == "done" and out["case"]["id"] == cid
    assert [d["filename"] for d in out["case"]["documents"]] == ["statement.pdf", "note.pdf"]
    assert out["case"]["findings"]  # the edited statement raises something
    assert len(events_of(client, cid, "file_ingested")) == 2 and events_of(client, cid, "dossier_generated")


def test_page_png_served_and_unknown_case_404(case):
    client, cid, data = case
    r = client.get(f"/api/cases/{cid}/pages/D1/1.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content == (data / "cases" / cid / "pages" / "D1-p1.png").read_bytes() and r.content.startswith(b"\x89PNG")
    assert client.get(f"/api/cases/{cid}").json()["status"] == "done"  # a case from an earlier session was finished then
    for url in (f"/api/cases/{ABSENT}", f"/api/cases/{ABSENT}/pages/D1/1.png", f"/api/cases/{cid}/pages/D1/99.png",
                f"/api/cases/{cid}/pages/D9/1.png", f"/api/cases/{cid}/pages/D1/0.png", f"/api/cases/{cid}/pages/..%2Fx/1.png",
                f"/api/cases/{cid}/pages/..%5Cpages%5CD1/1.png"):  # the last one is a real file on Windows, where a backslash is a separator
        assert client.get(url).status_code == 404, url


@pytest.mark.parametrize("bad", ["..%2F..%2Fsecret.txt", "..%5C..%5Csecret.txt", "%2e%2e", "C-1", "c-20260101-000000-abcd",
                                 "C-20260101-000000-abcd%00", "C-20260101-000000-abcd%2F..%2F..%2Fsecret.txt"])
def test_traversal_case_id_rejected(case, bad):
    client, _, data = case
    (data / "secret.txt").write_text("not for the browser")
    for suffix in ("", "/audit", "/dossier", "/dossier.json", "/pages/D1/1.png", "/crops/F-001-1.png", "/findings/F-001/review"):
        sent = client.post(f"/api/cases/{bad}{suffix}", json={"note": "x"}) if suffix.endswith("/review") else client.get(f"/api/cases/{bad}{suffix}")
        assert sent.status_code in (404, 405), (bad, suffix, sent.status_code)
        assert "not for the browser" not in sent.text


@pytest.mark.parametrize("name", ["../../evil.pdf", "..\\..\\evil.pdf", "/abs/evil.pdf", "C:\\evil.pdf"])
def test_hostile_filename_is_not_a_path(tmp_path, name):
    client = make_client(tmp_path / "data")
    pdf = pdf_bytes()
    cid = upload(client, (name, pdf))
    doc = wait_done(client, cid)["case"]["documents"][0]
    assert doc["filename"].endswith("evil.pdf")  # shown, never used as a path
    assert doc["stored_path"] == f"files/{hashlib.sha256(pdf).hexdigest()}.pdf"
    assert (tmp_path / "data" / "cases" / cid / doc["stored_path"]).read_bytes() == pdf
    assert not list(tmp_path.rglob("*evil*"))


def test_oversize_upload_rejected_with_reason(tmp_path):
    client = make_client(tmp_path / "data", Thresholds(max_file_bytes=3000))
    big, small = pdf_bytes() + bytes(5000), pdf_bytes()  # a readable PDF, refused only for its size (page text is compressed, so padding it is not enough)
    assert len(big) > 3000 > len(small)
    out = wait_done(client, upload(client, ("big.pdf", big), ("small.pdf", small)))
    assert [d["filename"] for d in out["case"]["documents"]] == ["small.pdf"]
    lim = [f for f in out["case"]["findings"] if f["title"].startswith("File not ingested")]
    assert len(lim) == 1 and "too large" in lim[0]["detail"] and "big.pdf" in lim[0]["detail"]
    rejected = events_of(client, out["case"]["id"], "file_rejected")
    assert len(rejected) == 1 and "too large" in rejected[0]["data"]["reason"]


def test_a_request_over_the_total_limit_is_refused_before_it_is_read(tmp_path):
    client = make_client(tmp_path / "data", Thresholds(max_file_bytes=1000, max_docs=2))
    r = client.post("/api/cases", files=[("files", ("a.pdf", bytes(1_200_000)))])
    assert r.status_code == 413 and "limit" in r.json()["detail"]
    assert not (tmp_path / "data" / "cases").exists()  # no case was made


@pytest.mark.parametrize("send", [dict(json={"files": 1}), dict(data={"note": "x"}), dict(files={"other": ("a.pdf", b"%PDF-")})])
def test_an_upload_without_files_is_refused_with_a_reason(tmp_path, send):
    client = make_client(tmp_path / "data")
    r = client.post("/api/cases", **send)
    assert r.status_code == 400 and "files" in r.json()["detail"]
    assert not (tmp_path / "data" / "cases").exists()


def test_ui_never_uses_innerhtml():
    files = [p for p in STATIC.iterdir() if p.suffix in (".js", ".html")]
    assert {p.name for p in files} >= {"app.js", "index.html"}
    for p in files:
        text = p.read_text(encoding="utf-8")
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert banned not in text, (p.name, banned)


def test_ui_loads_nothing_from_outside_and_has_no_inline_code():
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    for p in STATIC.iterdir():
        assert not re.search(r"https?://(?!www\.w3\.org/2000/svg)", p.read_text(encoding="utf-8")), p.name
    assert not re.search(r"<script(?![^>]*\bsrc=)", index) and not re.search(r"\son[a-z]+\s*=", index) and not re.search(r"\sstyle\s*=", index)


def test_ui_labels_match_the_dossier_and_say_no_verdict():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    for label in [*CLASS_LABEL.values(), *SOURCE_LABEL.values(), READING_LABEL]:
        assert label in js, label
    for p in STATIC.iterdir():
        assert not VERDICT.search(p.read_text(encoding="utf-8")), p.name


def test_index_has_all_tabs(case):
    client, _, _ = case
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    for tab in ("documents", "findings", "clusters", "audit", "capabilities", "dossier"):
        assert f'data-tab="{tab}"' in r.text and f'id="tab-{tab}"' in r.text, tab
    csp = r.headers["content-security-policy"]
    for directive in ("default-src 'none'", "script-src 'self'", "style-src 'self'", "img-src 'self' data:", "connect-src 'self'",
                      "base-uri 'none'", "form-action 'none'", "frame-ancestors 'none'"):
        assert directive in csp, directive
    assert "'unsafe-inline'" not in csp and "'unsafe-eval'" not in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert all(client.get(f"/static/{n}").status_code == 200 for n in ("app.js", "style.css"))


def test_only_the_two_assets_are_served_from_static(case):
    client, _, _ = case
    for name in ("index.html", "nope.js", "..%5Capp.py", "%2e%2e%2fapp.py", "app.js%00"):
        assert client.get(f"/static/{name}").status_code == 404, name


def test_upload_of_only_rejected_files_finishes_with_limitations(tmp_path):
    client = make_client(tmp_path / "data")
    cid = upload(client, ("notes.txt", b"just text"), ("empty.pdf", b""))
    out = wait_done(client, cid)
    assert out["status"] == "done" and out["case"]["documents"] == []
    assert [f["fclass"] for f in out["case"]["findings"]] == ["processing_limitation"] * 2
    assert client.get(f"/api/cases/{cid}/dossier").status_code == 200


def test_serve_binds_loopback_only(tmp_path, monkeypatch):
    import uvicorn
    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(app=app, **kw))
    assert HOST == "127.0.0.1"
    assert cli.main(["serve", "--port", "8123", "--data", str(tmp_path)]) == 0
    assert seen["host"] == "127.0.0.1" and seen["port"] == 8123 and callable(seen["app"])
    with pytest.raises(SystemExit):  # there is no way to ask for another address
        cli.main(["serve", "--host", "0.0.0.0"])


def test_review_actions_are_audited(case):
    client, cid, data = case
    findings = client.get(f"/api/cases/{cid}").json()["case"]["findings"]
    fid = next(f["id"] for f in findings if f["fclass"] == "inconsistency")
    url = f"/api/cases/{cid}/findings/{fid}/review"
    r = client.post(url, json={"status": "needs_verification"})
    assert r.status_code == 200 and r.json()["id"] == fid and r.json()["status"] == "needs_verification"
    assert client.post(url, json={"status": "dismissed", "note": "Re-typed by the branch"}).status_code == 200
    r = client.post(url, json={"note": "Only a note now"})
    assert r.status_code == 200 and r.json()["status"] == "dismissed" and r.json()["note"] == "Only a note now"
    now = next(f for f in client.get(f"/api/cases/{cid}").json()["case"]["findings"] if f["id"] == fid)  # kept on disk
    assert (now["status"], now["note"]) == ("dismissed", "Only a note now")
    acts = events_of(client, cid, "reviewer_action")
    assert [(e["actor"], e["data"]["finding"], e["data"]["from"], e["data"]["to"]) for e in acts] == [
        ("reviewer", fid, "open", "needs_verification"), ("reviewer", fid, "needs_verification", "dismissed"),
        ("reviewer", fid, "dismissed", "dismissed")]
    assert acts[1]["data"]["note"] == "Re-typed by the branch" and acts[0]["data"]["note"] is None
    assert client.get(f"/api/cases/{cid}/audit").json()["chain_ok"] is True


@pytest.mark.parametrize("body, code", [({"status": "fraud"}, 422), ({}, 422), ({"status": "dismissed", "extra": 1}, 422),
                                        ({"note": "x" * 2001}, 422), ({"status": None, "note": None}, 422)])
def test_bad_review_requests_change_nothing(case, body, code):
    client, cid, _ = case
    assert client.post(f"/api/cases/{cid}/findings/F-001/review", json=body).status_code == code
    assert client.post(f"/api/cases/{cid}/findings/F-999/review", json={"note": "x"}).status_code == 404
    assert events_of(client, cid, "reviewer_action") == []
    assert client.get(f"/api/cases/{cid}").json()["case"]["findings"][0]["status"] == "open"


def test_foreign_host_and_cross_origin_post_are_refused(case):
    client, cid, _ = case
    for host in ("evil.example", "127.0.0.1.evil.example:8000", "[::2]:8000"):  # DNS rebinding
        assert client.get("/api/capabilities", headers={"Host": host}).status_code == 403, host
    assert all(client.get("/api/capabilities", headers={"Host": h}).status_code == 200 for h in ("localhost:8000", "127.0.0.1", "[::1]:8000"))
    url = f"/api/cases/{cid}/findings/F-001/review"
    for origin in ("http://evil.example", "null", "http://127.0.0.1:9999"):  # a page on another origin posting to the local app
        assert client.post(url, json={"note": "x"}, headers={"Origin": origin}).status_code == 403, origin
    assert client.post("/api/cases", files=[("files", ("a.pdf", pdf_bytes()))], headers={"Origin": "http://evil.example"}).status_code == 403
    assert events_of(client, cid, "reviewer_action") == []
    assert client.post(url, json={"note": "x"}, headers={"Origin": BASE}).status_code == 200


def test_api_docs_are_not_served(case):
    client, _, _ = case
    assert [client.get(p).status_code for p in ("/docs", "/redoc", "/openapi.json")] == [404, 404, 404]  # the docs page loads from a CDN


def test_case_is_withheld_while_processing(tmp_path, monkeypatch):
    gate, inside = threading.Event(), threading.Event()
    real = web.run_case

    def slow(cd, th=None, stages=None, on_stage=None):
        on_stage("read")
        inside.set()
        gate.wait(30)
        return real(cd, th, stages={}, on_stage=on_stage)

    monkeypatch.setattr(web, "run_case", slow)
    client = make_client(tmp_path / "data")
    pdf = pdf_bytes()
    cid = upload(client, ("a.pdf", pdf), ("notes.txt", b"just text"))
    assert inside.wait(10)
    try:
        s = client.get(f"/api/cases/{cid}").json()
        assert (s["status"], s["stage"], s["case"]) == ("processing", "read", None)  # case.json is being replaced stage by stage
        assert s["intake"]["accepted"] == [{"id": "D1", "filename": "a.pdf", "size": len(pdf)}]  # what the page shows while it waits
        assert len(s["intake"]["rejected"]) == 1 and "notes.txt" in s["intake"]["rejected"][0]
        assert s["low_conf"] == Thresholds().low_conf
        for url in ("/audit", "/dossier", "/dossier.json", "/pages/D1/1.png", "/crops/F-001-1.png"):
            assert client.get(f"/api/cases/{cid}{url}").status_code == 409, url
        assert client.post(f"/api/cases/{cid}/findings/F-001/review", json={"note": "x"}).status_code == 409
    finally:
        gate.set()
    out = wait_done(client, cid)
    assert out["status"] == "done" and out["case"]["documents"][0]["filename"] == "a.pdf"


def test_a_crashed_run_is_reported_as_failed(tmp_path, monkeypatch):
    def boom(cd, th=None, stages=None, on_stage=None):
        raise RuntimeError("disk full")

    monkeypatch.setattr(web, "run_case", boom)
    client = make_client(tmp_path / "data")
    cid = upload(client, ("a.pdf", pdf_bytes()))
    out = wait_done(client, cid)
    assert out["status"] == "failed" and "disk full" in out["error"] and out["case"]["documents"]  # what was ingested is still shown
    assert len(events_of(client, cid, "run_failed")) == 1


def test_a_case_left_unfinished_by_a_stopped_server_is_not_called_done(tmp_path):
    _, cd, _ = create_case(tmp_path / "data", [("a.pdf", pdf_bytes())], Thresholds())  # ingested, never run
    s = make_client(tmp_path / "data").get(f"/api/cases/{cd.id}").json()
    assert s["status"] == "failed" and "interrupted" in s["error"] and s["case"]["documents"]


def test_a_case_stopped_part_way_is_not_called_done(tmp_path):
    _, cd, _ = create_case(tmp_path / "data", [("a.pdf", pdf_bytes())], Thresholds())
    AuditLog(cd.audit_path).append("system", "stage_end", {"stage": "read", "ok": True})  # the first stage ended, the last never did
    s = make_client(tmp_path / "data").get(f"/api/cases/{cd.id}").json()
    assert s["status"] == "failed" and "interrupted" in s["error"]


def test_a_file_is_read_only_up_to_one_byte_over_the_limit(tmp_path, monkeypatch):
    seen, real = [], web.create_case

    def spy(root, named, th):
        seen.extend(len(data) for _, data in named)
        return real(root, named, th)

    monkeypatch.setattr(web, "create_case", spy)
    client = make_client(tmp_path / "data", Thresholds(max_file_bytes=3000))
    wait_done(client, upload(client, ("big.pdf", pdf_bytes() + bytes(5000))))
    assert seen == [3001]  # enough to see the file is over, no more held in memory


def test_dossier_download_is_built_fresh_and_audited(case):
    client, cid, _ = case
    note = "Branch confirmed the entry by phone"
    assert client.post(f"/api/cases/{cid}/findings/F-001/review", json={"status": "confirmed_by_reviewer", "note": note}).status_code == 200
    before = len(events_of(client, cid, "dossier_generated"))
    r = client.get(f"/api/cases/{cid}/dossier")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "attachment" in r.headers["content-disposition"] and cid in r.headers["content-disposition"]
    assert "confirmed_by_reviewer" in r.text and note in r.text  # what the reviewer did is in the dossier
    j = client.get(f"/api/cases/{cid}/dossier.json")
    assert j.status_code == 200 and "attachment" in j.headers["content-disposition"] and len(j.json()["integrity"]["json_sha256"]) == 64
    assert len(events_of(client, cid, "dossier_generated")) == before + 2 and client.get(f"/api/cases/{cid}/audit").json()["chain_ok"]


def test_crop_names_are_validated(case):
    client, cid, data = case
    crop = next((data / "cases" / cid / "crops").glob("F-*.png"))
    r = client.get(f"/api/cases/{cid}/crops/{crop.name}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == crop.read_bytes()
    for name in ("..%2Fcase.json", "..%5Ccase.json", "case.json", "F-001-1.PNG", f"{crop.name}%00", "F-999-9.png", "%2e%2e%2fcase.json"):
        assert client.get(f"/api/cases/{cid}/crops/{name}").status_code == 404, name


def test_a_model_reading_saved_with_the_case_reaches_the_page_and_the_dossier(case):
    client, cid, data = case
    assert client.get(f"/api/cases/{cid}").json()["case"]["reasoning"] is None
    assert client.get(f"/api/cases/{cid}/dossier.json").json()["investigation_summary"]["ai_reading"]["status"] == "none"
    cd = CaseDir.open(data, cid)
    saved = load_case(cd)
    a, b = saved.findings[0].id, saved.findings[1].id
    saved.reasoning = Reasoning(model="qwen3:4b", summary=f"Read {a} first.", relations=[Relation(a=a, b=b, kind="same_field", reason="Same field.")])
    save_case(saved, cd)
    got = client.get(f"/api/cases/{cid}").json()["case"]["reasoning"]
    assert (got["source"], got["model"], got["relations"][0]["kind"]) == ("llm", "qwen3:4b", "same_field")
    shown = client.get(f"/api/cases/{cid}/dossier.json").json()["investigation_summary"]["ai_reading"]
    assert shown["status"] == "kept" and shown["summary"] == f"Read {a} first."
    assert READING_LABEL in client.get(f"/api/cases/{cid}/dossier").text


def test_capabilities_are_served_from_the_one_matrix(case):
    client, _, _ = case
    assert client.get("/api/capabilities").json() == load_capabilities()


def test_audit_endpoint_reports_a_broken_chain(case):
    client, cid, data = case
    a = client.get(f"/api/cases/{cid}/audit").json()
    assert a["chain_ok"] is True and a["problem"] is None and a["events"][0]["event"] == "case_created"
    path = data / "cases" / cid / "audit.jsonl"
    lines = path.read_bytes().splitlines()
    lines[1] = lines[1].replace(b"file_ingested", b"file_ingestes")
    path.write_bytes(b"\n".join(lines) + b"\n")
    b = client.get(f"/api/cases/{cid}/audit").json()
    assert b["chain_ok"] is False and "event 2" in b["problem"]
