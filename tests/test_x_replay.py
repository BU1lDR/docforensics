"""The numbers in eval/x and docs/spike-x-extraction.md are the scores of this code on the replies a model gave on 5 Nov. The replies are
kept in the .json beside each report, so anyone can score them again without the model; this test does it for the first two cases of the
phi4-mini run (one digital pair, one scanned pair, so the OCR runs) and expects the counts that were written down."""
import json
from pathlib import Path

import pytest

from evaluation.run_x import run
from evaluation.score_x import summarise

SAVED = Path(__file__).resolve().parents[1] / "eval" / "x" / "ext-dev-phi4-mini-3-8b.json"


@pytest.mark.ocr
def test_the_saved_replies_give_the_scores_that_were_written_down(tmp_path):
    kept = json.loads(SAVED.read_text(encoding="utf-8"))
    again = run("ext-dev", 2, 0, tmp_path, replay=SAVED)
    want = summarise(kept["results"][:2])
    assert again["outcomes"] == want["outcomes"] and again["facts"] == want["facts"] == 52
    assert again["extras"] == want["extras"] and again["seconds"] == want["seconds"]
    assert again["run"]["model"] == kept["run"]["model"] == "phi4-mini:3.8b" and again["run"]["replayed"] is True
