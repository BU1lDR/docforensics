"""The report of evaluation/run_h.py, on rows made by hand: its counts and tables follow the rows."""
from evaluation.run_h import format_report

RUN = {"split": "ext-dev", "when": "06 Nov 2026 13:00", "commit": "abc1234", "dirty": False, "seconds": 12.0, "peak_mb": 700.0, "machine": "Windows, Python 3.11"}


def row(case, kind, medium, found, stray, *pairs):
    return {"case": case, "kind": kind, "medium": medium, "layout": "A", "seconds": 1.0, "found": found, "stray": stray,
            "compared": kind == "genuine" or any(k == kind for k, _, _ in pairs),
            "pairs": [{"kind": k, "ink": ink, "hash_bits": bits, "repeat": ink <= 5.0} for k, ink, bits in pairs]}


ROWS = [row("c0", "genuine", "digital", False, 1, ("signature", 4.0, 2)),
        row("c1", "signature", "digital", True, 0, ("signature", 0.0, 0)),
        row("c2", "signature", "150dpi", False, 0, ("signature", 6.0, 8)),
        row("c3", "stamp", "digital", False, 0, ("signature", 30.0, 6))]


def test_the_report_counts_the_finds_the_strays_and_the_stamp_cases_it_did_not_compare():
    text = format_report(ROWS, RUN)
    assert "| **signature** | all | 2 | 1 | 0 | 0 |" in text
    assert "| **stamp** | all | 1 | 0 | 1 | 0 |" in text  # a stamp case is listed, and is not compared
    assert "| **all** | 1 | 1 | 1 |" in text  # the genuine case with a false observation


def test_the_report_sets_the_repeated_pairs_against_the_separate_ones_by_gap_and_by_hash():
    text = format_report(ROWS, RUN)
    assert "| repeated | all | 2 | 0.0 | 3.0 | 6.0 |" in text and "| separate | all | 2 | 4.0 | 17.0 | 30.0 |" in text
    assert "| 5 | 1 of 2 | 1 of 2 |" in text  # at a limit of 5 %: one repeated pair found, one separate pair flagged
    assert "| repeated | all | 2 | 0 | 4 | 8 |" in text and "| separate | all | 2 | 2 | 4 | 6 |" in text
    assert "(8 bits): 2 of 2." in text  # the hash does not tell the pairs apart here


def test_a_run_without_a_compared_pair_still_reports():
    text = format_report([row("c3", "stamp", "digital", False, 0)], RUN)
    assert "| **stamp** | all | 1 | 0 | 1 | 0 |" in text and "| repeated | all | 0 | - | - | - |" in text
