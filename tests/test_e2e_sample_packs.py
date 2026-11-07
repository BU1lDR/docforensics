"""The demo cases of the two newer checks (sample_data/): three of the reused-signature check and three of the compression-history check, all
of the ext-dev split of the packs made for them (datagen/reuse_pack.py, datagen/ela_pack.py). Each case goes through the whole pipeline in a
temporary folder, with connections to public addresses blocked (conftest.py), and what comes out is compared with what sample_data/README.md
says of it, as tests/test_e2e_sample.py does for the five cases of the development split.

ext-dev is the split on which the two checks were set up (their constants and limits were fitted on it), so these cases show the checks working
from files to dossier and say nothing about how well they detect. Which case is here, and why, is written in sample_data/README.md."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from datagen.sample import MANIFESTS, PACK_NAME, PACK_SPLIT, PACKS, build_sample
from docforensics.audit import AuditLog
from docforensics.cli import main
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import STAGE_ORDER, run_case
from evaluation.run_e import LOCATED, LOW, touches
from evaluation.score import PLACE, iou

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data"
NAMES = [name for names in PACKS.values() for name in names]
SCANNED = {"ext-dev-h-0046", "ext-dev-e-0000", "ext-dev-e-0002", "ext-dev-e-0012"}  # a scan loads the OCR engine; the other two are digital PDFs

# What the pipeline raises on each case, as (detector, class), exactly this and nothing else. The limitations are not the two checks' own: the
# checks that read figures off a 120 dpi scan raise them, and so does the cross-document step on a case of one document (every compression-history case).
RAISES = {
    "ext-dev-h-0000": Counter(),
    "ext-dev-h-0001": Counter({("reuse", "observation"): 1}),
    "ext-dev-h-0046": Counter({(d, "processing_limitation"): 1 for d in ("statement_checks", "payslip_checks", "cross_checks", "context_emi")}),
    "ext-dev-e-0000": Counter({("cross_checks", "processing_limitation"): 1}),
    "ext-dev-e-0002": Counter({("ela", "observation"): 1, ("payslip_sums", "inconsistency"): 1, ("payslip_words", "inconsistency"): 1,
                               ("cross_checks", "processing_limitation"): 1, ("link", "potential_manipulation"): 1}),
    "ext-dev-e-0012": Counter({(d, "processing_limitation"): 1 for d in ("payslip_checks", "cross_checks")}),
}
# reused-signature check, case: (the ink gap in % that the audit trail logs for the pair of signatures, whether the pair is called the same image,
# the bits that differ between the pair's 64-bit hashes, which are logged and do not decide)
REUSE = {"ext-dev-h-0000": (17.73, False, 5), "ext-dev-h-0001": (0.0, True, 0), "ext-dev-h-0046": (6.72, False, 3)}
# compression-history check, case: (regions it reports, whether one is at the planted place, whether the picture's last save is below what it can examine)
HISTORY = {"ext-dev-e-0000": (0, False, False), "ext-dev-e-0002": (1, True, False), "ext-dev-e-0012": (0, False, True)}


def manifest(kind: str) -> dict:
    return json.loads((SAMPLE / MANIFESTS[kind]).read_text(encoding="utf-8"))


def entry_of(name: str) -> dict:
    kind = name.split("-")[2]  # ext-dev-<h or e>-<number>
    return next(e for e in manifest(kind)["cases"] if e["case"] == name)


def files_of(name: str) -> list[tuple[str, bytes]]:
    """The files of a case in the order `docforensics run <folder>` reads them: by name."""
    return [(p.name, p.read_bytes()) for p in sorted((SAMPLE / name).iterdir()) if p.is_file()]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hashes_of(entry: dict) -> dict[str, str]:
    """What a manifest entry says of its files, by name: the documents of a case of the reuse pack, the one scan of a case of the other."""
    return {d["file"]: d["sha256"] for d in entry["docs"]} if "docs" in entry else {entry["file"]: entry["sha256"]}


def section(doc: str, name: str) -> str:
    """The README's part on one case: from its '### <case>' heading to the next heading."""
    found = re.search(rf"^### {re.escape(name)}\b.*?(?=^#{{1,3}} |\Z)", doc, re.M | re.S)
    assert found, f"sample_data/README.md has no section on {name}"
    return found.group(0)


@pytest.mark.parametrize("kind", PACKS)
def test_the_manifest_of_a_pack_describes_the_files_beside_it(kind):
    m = manifest(kind)
    assert (m["split"], m["pack"]) == (PACK_SPLIT, PACK_NAME[kind])
    assert [e["case"] for e in m["cases"]] == list(PACKS[kind])
    for e in m["cases"]:
        assert {n: sha256(d) for n, d in files_of(e["case"])} == hashes_of(e), e["case"]


def test_the_pack_cases_can_be_built_again(tmp_path):
    build_sample(tmp_path)
    for kind, names in PACKS.items():
        built = json.loads((tmp_path / MANIFESTS[kind]).read_text(encoding="utf-8"))
        assert (built["split"], built["pack"], [e["case"] for e in built["cases"]]) == (PACK_SPLIT, PACK_NAME[kind], list(names))
        for e in built["cases"]:  # what was written is what the manifest says was written
            assert {p.name: sha256(p.read_bytes()) for p in (tmp_path / e["case"]).iterdir()} == hashes_of(e), e["case"]


@pytest.mark.parametrize("name", [pytest.param(n, marks=pytest.mark.ocr) if n in SCANNED else n for n in NAMES])
def test_a_pack_case_runs_end_to_end(tmp_path, name):
    entry, th = entry_of(name), Thresholds()
    _, cd, _ = create_case(tmp_path / "data", files_of(name), th)
    case = run_case(cd, th)
    assert Counter((f.detector, f.fclass) for f in case.findings) == RAISES[name]

    # read and understood: every file is a document under the hash the manifest holds, a scan read through OCR and a digital document through its text layer
    assert {d.filename: d.sha256 for d in case.documents} == hashes_of(entry)
    assert [d.doc_type for d in case.documents] == ([d["type"] for d in entry["docs"]] if "docs" in entry else ["payslip"])
    assert {p.read_mode for d in case.documents for p in d.pages} == ({"ocr"} if name in SCANNED else {"text-layer"})

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
    assert shas == hashes_of(entry)
    trace = dossier["evidence_and_traceability"]["trace"]
    assert all(row["sha256"] == shas[row["file"]] for row in trace)
    assert all((cd.root / row["crop"]).is_file() for row in trace if row["crop"])

    # what the check of the case did, counted as the evaluation counts it (evaluation/run_h.py, evaluation/run_e.py)
    figures = []  # what the README's section on the case has to give, besides the titles
    if name in REUSE:
        ink, same, bits = REUSE[name]
        (pair,) = [e.data for e in events if e.event == "reuse_compared"]
        assert pair["ink"] == pytest.approx(ink, abs=0.05) and pair["repeat"] is same and pair["hash_bits"] == bits
        # the comparison is in the dossier's audit trail whatever it found; a finding is there only when the pair is called the same image
        assert [e["data"]["ink"] for e in dossier["appendices"]["audit_trail"]["events"] if e["event"] == "reuse_compared"] == [pair["ink"]]
        names = {c.id: c.filename for c in case.documents}
        truth = {n: b[1:] for n, b in entry["reuse"][0]["boxes"].items()} if entry["reuse"] else {}
        mine = [f for f in case.findings if f.detector == "reuse"]
        at = [f for f in mine if len(f.evidence) == 2 and {names[e.doc] for e in f.evidence} == set(truth)
              and all(iou(e.box, truth[names[e.doc]]) >= PLACE for e in f.evidence)]
        assert len(mine) == len(at) == int(same)  # found at its place and no stray one, or nothing at all
        figures = [f"{pair['ink']:.1f}", f"limit of {pair['limit_ink']:g} %", "do not differ" if bits == 0 else f"{bits} bits apart"]
        if at:  # the finding leads to the two documents that carry the signature, and its boxes lie on the planted ones
            assert {row["file"] for row in trace if row["finding"] == at[0].id} == set(truth)
            assert all(iou(e.box, truth[names[e.doc]]) > 0.9 for e in at[0].evidence)
            figures.append("more than 0.9")
    else:
        regions, located, cannot = HISTORY[name]
        mine = [f for f in case.findings if f.detector == "ela"]
        boxes = [list(ev.box) for f in mine for ev in f.evidence]
        assert len(boxes) == regions and all(f.fclass == "observation" for f in mine)
        assert (bool(entry["box"]) and any(iou(b, entry["box"]) > LOCATED for b in boxes)) is located
        assert all(touches(b, entry["box"]) for b in boxes)  # none is a stray region
        assert (entry["final_quality"] < LOW) is cannot
        # the check ran on the picture and the audit trail says how many findings it made. For a picture it cannot examine that is the same line as for
        # one it examined and found clean: nothing in the case says which of the two happened (the README says so, and the capability matrix holds the limit)
        (ran,) = [e.data for e in events if e.event == "doc_forensics" and e.data["detector"] == "jpeg_history"]
        assert ran["findings"] == len(mine)
        figures = [f"quality {entry['final_quality']}"]  # the picture's last save, which the README gives for every case
        if entry["host_quality"] != entry["final_quality"]:
            figures.append(f"quality {entry['host_quality']}")  # a page saved twice: the earlier save too
        if cannot:
            figures.append(f"quality {LOW}")
        if mine:  # the finding leads to the scan, with a marked crop, and says which earlier save it found no trace of
            assert [row["file"] for row in trace if row["finding"] == mine[0].id and row["crop"]] == [entry["file"]]
            earlier = re.search(r"quality (\d+) changes its ink by", mine[0].evidence[0].note).group(1)
            assert int(earlier) == entry["host_quality"]
            best = max(iou(b, entry["box"]) for b in boxes)
            figures += [mine[0].evidence[0].note, f"{best:.2f}", "{} and {} pixels".format(*entry["shift"])]

    # the README's section on the case gives every finding by its title and these figures
    text = section((SAMPLE / "README.md").read_text(encoding="utf-8"), name)
    assert [f.title for f in case.findings if f.title not in text] == []
    assert [x for x in figures if x not in text] == []


def test_the_quick_start_works_on_a_pack_case(tmp_path, capsys):
    data = str(tmp_path / "data")
    assert main(["run", str(SAMPLE / "ext-dev-h-0001"), "--data", data]) == 0
    out = capsys.readouterr().out
    case_id = re.search(r"^Case (C-\d{8}-\d{6}-[0-9a-f]{4})", out, re.M).group(1)
    assert "are the same image" in out
    finding = re.search(rf"docforensics trace {case_id} (F-\d+)", out).group(1)
    assert main(["trace", case_id, finding, "--data", data]) == 0
    assert "stored file matches" in capsys.readouterr().out


def test_the_sample_readme_names_every_pack_case_and_says_they_are_in_sample():
    doc = (SAMPLE / "README.md").read_text(encoding="utf-8")
    assert [name for name in NAMES if name not in doc] == []
    assert PACK_SPLIT in doc and "in-sample" in doc and "test_e2e_sample_packs.py" in doc
