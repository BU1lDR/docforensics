"""The compression-history check inside the whole tool (scope D, package E): an uploaded JPEG scan goes through the reader, OCR, the checks
and the explanation stage, and the dossier carries what the check found, or nothing. Marked ocr: it runs the OCR engine on each page."""
import pytest

from datagen.ela_pack import build_case, plan_cases
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from tests.helpers import iou

pytestmark = pytest.mark.ocr
TH = Thresholds()
PLAN = {(p["kind"], p["level"]): p for p in plan_cases("ext-dev", 36)}


def run(kind, tmp_path, level="150dpi"):
    scan, entry = build_case(PLAN[kind, level])
    _, cd, _ = create_case(tmp_path / "data", [("scan.jpg", scan)], TH)
    return run_case(cd, TH), entry


def test_a_piece_pasted_into_an_uploaded_scan_is_an_observation_at_its_place_with_its_own_explanation(tmp_path):
    case, entry = run("pasted-field", tmp_path)
    (f,) = [f for f in case.findings if f.detector == "ela"]
    assert f.fclass == "observation" and max(iou(ev.box, entry["box"]) for ev in f.evidence) > 0.3
    assert "ordinary causes" in f.explanation and f.next_steps and f.explanation_source == "template"
    assert all(ev.crop_path for ev in f.evidence)  # the marked crops of the dossier exist


@pytest.mark.parametrize("kind", ["genuine", "resaved"])
def test_a_scan_saved_once_and_the_same_scan_saved_again_give_the_check_nothing_to_say(tmp_path, kind):
    case, _ = run(kind, tmp_path)
    assert [f for f in case.findings if f.detector == "ela"] == []
