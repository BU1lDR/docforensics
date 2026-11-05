"""The sample data (Task 24): five small cases that a judge can run with one command, and the end-to-end check that the README's quick
start is true. Each case goes through the whole pipeline in a temporary folder and is scored the way the evaluation scores a case
(evaluation/score.py), and what comes out is compared with what sample_data/README.md says of it.

The cases are cases of the development split, on which the thresholds were tuned. Running them shows the tool working from files to
dossier; it is not evidence of how well the tool detects. The held-out figures are in eval/test.md.

Every test that runs the pipeline is a function-scoped test, so the autouse guard in conftest.py that blocks public addresses is in
force while the tool runs: the claim that a case needs no network is checked here, not assumed."""
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from datagen.sample import CASES as BUILT, SPLIT, build_sample
from docforensics.audit import AuditLog
from docforensics.cli import main
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import STAGE_ORDER, run_case
from evaluation.score import score

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data"
VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)  # as in test_readme: the documents give no verdict either
UTC = timedelta(0)

# case: (change planted, found, located). The values are what the pipeline returns on these files, as sample_data/README.md says; a change in
# the pipeline that moves one of them makes this fail until the README is brought in line.
EXPECT = {
    "dev-0000": ("D1", True, True),
    "dev-0002": (None, None, None),
    "dev-0006": ("S1", True, True),
    "dev-0009": ("C2", True, None),
    "dev-0043": ("C5", False, None),
}
# What each case raises, as (detector, class), exactly this and nothing else. dev-0006 is found through the payslip's own arithmetic and the
# comparison of the declared income with it: neither scan check (scan_noise, scan_layout) raised anything on the spliced part.
RAISES = {
    "dev-0000": Counter({("pdf_revisions", "observation"): 1, ("statement_balance", "inconsistency"): 1, ("link", "potential_manipulation"): 1}),
    "dev-0002": Counter(),
    "dev-0006": Counter({("payslip_sums", "inconsistency"): 2, ("cross_income", "inconsistency"): 1, ("link", "potential_manipulation"): 1}),
    "dev-0009": Counter({("cross_name", "inconsistency"): 1}),
    "dev-0043": Counter(),
}
CASES = [pytest.param(name, marks=pytest.mark.ocr) if EXPECT[name][0] == "S1" else name for name in EXPECT]  # a scan loads the OCR engine


def manifest() -> dict:
    return json.loads((SAMPLE / "manifest.json").read_text(encoding="utf-8"))


def entry_of(name: str) -> dict:
    return next(e for e in manifest()["cases"] if e["case"] == name)


def files_of(name: str) -> list[tuple[str, bytes]]:
    """The files of a case in the order `docforensics run <folder>` reads them: by name."""
    return [(p.name, p.read_bytes()) for p in sorted((SAMPLE / name).iterdir()) if p.is_file()]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def moment(text: str) -> datetime:
    return datetime.fromisoformat(text)


def test_the_manifest_describes_the_files_beside_it():
    m = manifest()
    assert m["split"] == "dev"
    assert [e["case"] for e in m["cases"]] == list(EXPECT) == sorted(p.name for p in SAMPLE.iterdir() if p.is_dir())
    for e in m["cases"]:
        assert {n: sha256(d) for n, d in files_of(e["case"])} == {d["file"]: d["sha256"] for d in e["docs"]}, e["case"]


def test_the_sample_has_digital_and_scanned_genuine_and_changed_cases():
    entries = manifest()["cases"]
    assert [(e["manipulations"][0]["method"] if e["manipulations"] else None) for e in entries] == [v[0] for v in EXPECT.values()]
    assert {e["genuine"] for e in entries} == {True, False} and {e["medium"] == "digital" for e in entries} == {True, False}
    for e in entries:  # the medium is what the files are: a scan is a picture, a digital document a PDF
        assert {Path(d["file"]).suffix for d in e["docs"]} == ({".pdf"} if e["medium"] == "digital" else {".jpg"}), e["case"]


@pytest.mark.parametrize("name", CASES)
def test_a_sample_case_runs_end_to_end(tmp_path, name):
    entry, (method, found, located) = entry_of(name), EXPECT[name]
    th = Thresholds()
    case, cd, _ = create_case(tmp_path / "data", files_of(name), th)
    case = run_case(cd, th)
    assert Counter((f.detector, f.fclass) for f in case.findings) == RAISES[name]

    # read and understood: every file is a document of the type the manifest says it is, stored under the hash the manifest holds
    assert [(d.filename, d.doc_type, d.sha256) for d in case.documents] == [(d["file"], d["type"], d["sha256"]) for d in entry["docs"]]
    assert {p.read_mode for d in case.documents for p in d.pages} == ({"text-layer"} if entry["medium"] == "digital" else {"ocr"})

    # found or missed, as the evaluation counts it
    res = score({"split": "dev", "cases": [entry]}, {name: case}, {})
    if entry["genuine"]:
        assert (res["genuine"]["cases"], res["genuine"]["flags"]) == (1, 0)  # nothing is flagged on a genuine case; limitations may be raised
    else:
        assert list(res["methods"]) == [method]
        got = res["methods"][method]
        assert (got["n"], got["found"], got["located"]) == (1, int(found), None if located is None else int(located))
        assert [(m["case"], m["method"]) for m in res["misses"]] == ([] if found else [(name, method)])
        if not found:  # a miss is reported as a miss: the case yields no finding that cites the changed document
            assert res["misses"][0]["why"] == "no finding cites the changed document"

    # every step ran, in order, and the audit trail verifies
    log = AuditLog(cd.audit_path)
    events = log.events()
    assert log.verify() == (True, None) and events[0].event == "case_created"
    assert [e.data["stage"] for e in events if e.event == "stage_end" and e.data["ok"]] == list(STAGE_ORDER)
    assert not [e for e in events if e.event in ("stage_failed", "file_rejected")]

    # the dossier: written, about this case, and every file in it is the file in the manifest
    dossier = json.loads(cd.dossier_json.read_text(encoding="utf-8"))
    assert cd.dossier_html.is_file() and dossier["overview"]["case"] == case.id
    assert dossier["overview"]["counts"]["findings"] == len(case.findings)
    shas = {x["file"]: x["sha256"] for x in dossier["evidence_and_traceability"]["documents"]}
    assert shas == {d["file"]: d["sha256"] for d in entry["docs"]}
    trace = dossier["evidence_and_traceability"]["trace"]
    assert all(row["sha256"] == shas[row["file"]] for row in trace)
    assert all((cd.root / row["crop"]).is_file() for row in trace if row["crop"])
    if found:  # the finding that found the change leads to the changed document
        assert any(row["file"] == entry["manipulations"][0]["doc"] for row in trace)

    # times are UTC: the id, the case, the audit trail and the dossier, and they are the time of the run
    now = datetime.now(timezone.utc)
    stamps = [moment(case.created), moment(dossier["overview"]["generated"]), *(moment(e.ts) for e in events)]
    assert all(t.utcoffset() == UTC for t in stamps)
    in_id = datetime.strptime(case.id[2:17], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    assert all(timedelta(0) <= now - t < timedelta(minutes=10) for t in (in_id, *stamps))


def test_the_quick_start_commands_work_on_a_sample_case(tmp_path, capsys):
    data = str(tmp_path / "data")
    assert main(["run", str(SAMPLE / "dev-0000"), "--data", data]) == 0
    out = capsys.readouterr().out
    case_id = re.search(r"^Case (C-\d{8}-\d{6}-[0-9a-f]{4})", out, re.M).group(1)
    finding = re.search(rf"docforensics trace {case_id} (F-\d+)", out).group(1)
    assert main(["trace", case_id, finding, "--data", data]) == 0
    traced = capsys.readouterr().out
    assert "stored file matches" in traced and "sha256: " in traced and "location: page " in traced
    assert main(["verify-audit", case_id, "--data", data]) == 0
    assert capsys.readouterr().out.startswith("OK: ")


def test_the_sample_can_be_built_again(tmp_path):
    built = json.loads(build_sample(tmp_path).read_text(encoding="utf-8"))
    assert (SPLIT, tuple(e["case"] for e in built["cases"])) == (manifest()["split"], BUILT) and list(BUILT) == list(EXPECT)
    for e in built["cases"]:  # what was written is what the manifest says was written
        assert {p.name: sha256(p.read_bytes()) for p in (tmp_path / e["case"]).iterdir()} == {d["file"]: d["sha256"] for d in e["docs"]}


def test_the_sample_readme_names_every_case_and_gives_no_verdict():
    doc = (SAMPLE / "README.md").read_text(encoding="utf-8")
    assert all(name in doc for name in EXPECT), [name for name in EXPECT if name not in doc]
    assert "development split" in doc and "(../eval/test.md)" in doc  # what the cases are, and where the held-out figures are
    assert not VERDICT.search(doc), VERDICT.search(doc)
    for target in re.findall(r"\]\(([^)\s]+)\)", doc):  # a link that leads nowhere is a mistake in a document that points at evidence
        assert re.match(r"[a-z]+:", target) or (SAMPLE / target.partition("#")[0]).exists(), target
