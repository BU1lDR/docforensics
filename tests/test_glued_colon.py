"""A colon set directly against an amount ('Opening Balance as on 1 Jan 2026 :2,53,102.32') is read by OCR as part of the amount's word:
':2,53,102.32'. The amount was then not read, the statement was reported as not fully verifiable, and the stretch of the balance chain
from the opening balance to the first row was not tested (docs/probe.md, second probe). tests/fixtures/stored_statement_sbi_words.json is
page 1 of one such statement as stored (242 OCR words with their boxes, fictional). Only that shape is read: a colon in front of an
amount with cents, nothing else."""
import pytest

from docforensics.understand.extract import extract_document
from tests.test_extraction_layouts import read
from tests.test_merged_amount_cells import SPEC, TH, stored_statement


def opening(tmp_path, printed):
    got = read(tmp_path, [(40, 60, "Opening Balance as on 1 Jan 2026", 9), (300, 60, printed, 9)])[1]
    return got[("opening_balance", None)]


def test_the_opening_balance_of_the_stored_statement_is_read_with_the_colon_left_as_printed():
    got = {f.name: f for f in extract_document(stored_statement(), SPEC, TH) if f.row is None}
    f = got["opening_balance"]
    assert (f.value, f.raw, f.note) == ("253102.32", ":2,53,102.32", ""), (f.value, f.raw, f.note)
    assert f.conf >= TH.low_conf, f.conf


@pytest.mark.parametrize("printed,value", [(":2,53,102.32", "253102.32"), (":1,20,500.00", "120500.00"), (": 2,53,102.32", "253102.32")])
def test_a_colon_against_the_amount_or_beside_it_leaves_the_amount_read(tmp_path, printed, value):
    f = opening(tmp_path, printed)
    assert f.value == value, (f.value, f.raw, f.note)


@pytest.mark.parametrize("printed", ["12:30", ":2,53,102", "2,53,102.32:", "::2,53,102.32", ":Opening", "2,53,10:2.32"])
def test_any_other_shape_with_a_colon_stays_unread(tmp_path, printed):
    """Not a time, not an amount without cents, not a colon behind, not two colons: the value is not read, as before."""
    f = opening(tmp_path, printed)
    assert f.value is None, (f.value, f.raw, f.note)
