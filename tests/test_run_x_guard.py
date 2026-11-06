"""Guards of the X runner (scope D, package X). Two ways a run could leave a report that says nothing about the model: the held-out split
read twice, and a run in which the model was never there (Ollama down, the model not pulled, every call failing), whose report would score
a model that did not answer as having read nothing. No model runs here: a stand-in client answers, or `run` itself is replaced where only the
command line is under test."""
import pytest

from docforensics.explain.llm import LLMError
from evaluation import run_x
from evaluation.score_x import OUTCOMES


class Stub:
    """The client of a model that is not there (digest "") or that fails every call; it keeps what it was asked."""
    model, timeout = "stub-model:1b", 100.0

    def __init__(self, digest: str) -> None:
        self._digest, self.calls = digest, []

    def digest(self) -> str:
        return self._digest

    def chat_json(self, system, user, schema):
        self.calls.append(user)
        raise LLMError("connection refused")


def unreachable(*args, **kwargs):
    raise AssertionError("this must not be reached")


def test_ext_test_is_not_read_without_the_once_flag(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(run_x, "run", unreachable)
    with pytest.raises(SystemExit) as stop:
        run_x.main(["ext-test", "--out", str(tmp_path / "x")])
    assert stop.value.code not in (0, None) and "--once-at-freeze" in capsys.readouterr().err
    assert not (tmp_path / "x").exists()


@pytest.mark.parametrize("argv", [["ext-dev"], ["ext-test", "--once-at-freeze"]])
def test_ext_dev_runs_without_the_flag_and_ext_test_runs_with_it(monkeypatch, tmp_path, argv):
    seen = []

    def run(split, n, start, out, **kwargs):
        seen.append(split)
        return {"cases": 0, "facts": 0, "outcomes": dict.fromkeys(OUTCOMES, 0)}

    monkeypatch.setattr(run_x, "run", run)
    assert run_x.main([*argv, "--out", str(tmp_path)]) == 0 and seen == [argv[0]]


def test_a_model_ollama_does_not_have_stops_the_run_before_anything_is_built_or_written(monkeypatch, tmp_path):
    monkeypatch.setattr(run_x, "build_split", unreachable)  # not even the pack is made
    stub, out = Stub(digest=""), tmp_path / "x"
    with pytest.raises(run_x.NoModelReply, match="stub-model:1b"):
        run_x.run("ext-dev", 1, 0, out, client=stub)
    assert stub.calls == [] and not out.exists()


def test_a_model_that_fails_every_call_leaves_no_report(tmp_path):
    stub, out = Stub(digest="sha256:stub"), tmp_path / "x"
    with pytest.raises(run_x.NoModelReply, match="connection refused"):
        run_x.run("ext-dev", 1, 0, out, client=stub)
    assert stub.calls and not out.exists()  # it was asked, and every answer was an error


def test_main_says_so_and_exits_non_zero_when_the_model_is_not_there(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(run_x, "OllamaClient", lambda model: Stub(digest=""))
    assert run_x.main(["ext-dev", "--cases", "1", "--out", str(tmp_path / "x")]) == 1
    assert "no report was written" in capsys.readouterr().err and not (tmp_path / "x").exists()
