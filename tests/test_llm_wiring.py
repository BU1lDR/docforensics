"""The local model is opt-in. `--llm` on run and serve, and a review desk made with a client, build one client, check that Ollama has the
model before anything is made, and hand the client to the pipeline. Nothing here reaches Ollama: the client class is replaced."""
import pytest
from fastapi.testclient import TestClient

from docforensics import cli
from docforensics.explain.llm import DEFAULT_MODEL
from docforensics.model import Reasoning, Relation
from docforensics.web import app as web
from tests.helpers import pdf_bytes
from tests.test_llm_guard import Fake
from tests.test_web import BASE, upload, wait_done

READING = Reasoning(model="m:1b", summary="F-001 and F-002 both concern the net pay of D2.", order=["F-002", "F-001"],
                    relations=[Relation(a="F-001", b="F-002", kind="same_document", reason="Both concern the net pay line of D2.")])


@pytest.fixture
def ollama(monkeypatch):
    """OllamaClient as the command line sees it: only DEFAULT_MODEL and other:1b are listed by the server. `made` holds the clients built."""
    class Server:
        listed = [DEFAULT_MODEL, "other:1b"]
        made: list = []

    class Stub(Fake):
        def __init__(self, model):
            super().__init__(None)
            self.model = model
            Server.made.append(self)

        def digest(self):
            return "sha256:fakedigest" if self.model in Server.listed else ""

    monkeypatch.setattr(cli, "OllamaClient", Stub)
    return Server


@pytest.fixture
def pipeline(monkeypatch):
    """run_case for the command line and the review desk, with no stage run: it notes the client it was handed and returns `reading`."""
    seen = {}
    real = cli.run_case

    def spy(cd, th=None, stages=None, on_stage=None, llm=None):
        seen["llm"] = llm
        case = real(cd, th, stages={}, on_stage=on_stage, llm=llm)
        case.reasoning = seen.get("reading")
        return case

    monkeypatch.setattr(cli, "run_case", spy)
    monkeypatch.setattr(web, "run_case", spy)
    return seen


def run(tmp_path, capsys, *flags):
    (tmp_path / "in").mkdir(exist_ok=True)
    (tmp_path / "in" / "a.pdf").write_bytes(pdf_bytes())
    code = cli.main(["run", str(tmp_path / "in" / "a.pdf"), *flags, "--data", str(tmp_path / "data")])
    return code, capsys.readouterr()


def test_without_the_flag_there_is_no_client_and_no_reading(tmp_path, capsys, ollama, pipeline):
    pipeline["reading"] = None
    code, cap = run(tmp_path, capsys)
    assert code == 0 and pipeline["llm"] is None and ollama.made == [] and "inference" not in cap.out and "language model" not in cap.out.lower()


@pytest.mark.parametrize("flags, model", [(["--llm"], DEFAULT_MODEL), (["--llm", "--llm-model", "other:1b"], "other:1b"),
                                          (["--llm-model", "other:1b"], "other:1b")])  # a model that is named is a model that is wanted
def test_the_flag_hands_the_pipeline_one_client_and_the_reading_is_printed_as_inference(tmp_path, capsys, ollama, pipeline, flags, model):
    pipeline["reading"] = READING
    code, cap = run(tmp_path, capsys, *flags)
    (client,) = ollama.made
    assert code == 0 and pipeline["llm"] is client and client.model == model
    assert "by m:1b" in cap.out and "inference" in cap.out and "not a finding" in cap.out and READING.summary in cap.out
    assert "F-001 and F-002 (same_document): Both concern the net pay line of D2." in cap.out and "F-002, F-001" in cap.out


def test_the_flag_may_come_before_the_paths(tmp_path, capsys, ollama, pipeline):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "a.pdf").write_bytes(pdf_bytes())
    code = cli.main(["run", "--llm", str(tmp_path / "in" / "a.pdf"), "--data", str(tmp_path / "data")])
    assert code == 0 and pipeline["llm"] is ollama.made[0]


def test_a_run_that_got_no_reading_says_so_and_where_to_look(tmp_path, capsys, ollama, pipeline):
    pipeline["reading"] = None
    code, cap = run(tmp_path, capsys, "--llm")
    assert code == 0 and "no reading of the case was kept" in cap.out and "llm_reasoning" in cap.out and "inference" not in cap.out


def test_a_model_ollama_does_not_list_stops_the_run_before_any_case_is_made(tmp_path, capsys, ollama, pipeline):
    code, cap = run(tmp_path, capsys, "--llm-model", "missing:7b")
    assert code == 2 and "ollama pull missing:7b" in cap.err and "missing:7b" not in cap.out
    assert "llm" not in pipeline and not list((tmp_path / "data").glob("cases/*"))  # nothing ran, and no empty case was left behind


def serve(monkeypatch, tmp_path, *flags):
    import uvicorn
    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(ran=True))
    monkeypatch.setattr(web, "create_app", lambda data, th=None, llm=None: seen.update(llm=llm) or object())
    return cli.main(["serve", *flags, "--data", str(tmp_path)]), seen


def test_serve_with_the_flag_builds_the_review_desk_around_one_client(monkeypatch, tmp_path, ollama):
    code, seen = serve(monkeypatch, tmp_path, "--llm")
    assert code == 0 and seen["ran"] and seen["llm"] is ollama.made[0] and seen["llm"].model == DEFAULT_MODEL


def test_serve_without_the_flag_has_no_client(monkeypatch, tmp_path, ollama):
    code, seen = serve(monkeypatch, tmp_path)
    assert code == 0 and seen["llm"] is None and ollama.made == []


def test_serve_with_a_model_that_is_not_there_does_not_start(monkeypatch, tmp_path, capsys, ollama):
    code, seen = serve(monkeypatch, tmp_path, "--llm-model", "missing:7b")
    assert code == 2 and seen == {} and "ollama pull missing:7b" in capsys.readouterr().err


@pytest.mark.parametrize("client", [Fake(None), None])
def test_the_review_desk_hands_its_client_to_every_analysis(tmp_path, pipeline, client):
    desk = TestClient(web.create_app(tmp_path / "data", llm=client), base_url=BASE)
    cid = upload(desk, ("a.pdf", pdf_bytes()))
    assert wait_done(desk, cid)["status"] == "done" and pipeline["llm"] is client
