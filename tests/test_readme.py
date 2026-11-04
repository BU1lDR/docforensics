"""The README and the documents beside it (Task 24): what a judge or a new user reads first. They have to say who built the tool and with
what help, credit what it stands on, quote the capability matrix and the limitations as the code holds them, show commands that parse,
and point only at files that exist. A diagram that leaves out a stage of the pipeline would mislead, so that is checked too."""
import re
import shlex
from pathlib import Path

import pytest

from docforensics import cli
from docforensics.capabilities import limitations_markdown, load_capabilities, matrix_markdown, refresh
from docforensics.explain.templates import TEMPLATES
from docforensics.pipeline import STAGE_ORDER

ROOT = Path(__file__).resolve().parents[1]
README, ARCHITECTURE, LIMITATIONS = ROOT / "README.md", ROOT / "docs" / "architecture.md", ROOT / "docs" / "limitations.md"
STALE = "capabilities.json changed: rebuild the block with  python -m docforensics.capabilities --update"
VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)  # as in test_capabilities: static text gives no verdict either


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def between(doc: str, name: str) -> str:
    """What lies between <!-- name:start --> and <!-- name:end -->: the part of a document that the code writes."""
    m = re.search(rf"<!-- {name}:start -->\n(.*?)\n<!-- {name}:end -->", doc, re.S)
    assert m, f"no <!-- {name}:start --> ... <!-- {name}:end --> block"
    return m.group(1)


def packages(*files: str) -> set[str]:
    return {m.group(1).lower() for f in files for m in re.finditer(r"^([A-Za-z0-9_.-]+)==", text(ROOT / f), re.M)}


def test_readme_discloses_ai_and_credits():
    doc = text(README)
    low = doc.lower()
    assert re.search(r"^#+ AI assistance", doc, re.M) and "claude code" in low and "anthropic" in low
    pkgs = packages("requirements.txt", "requirements-dev.txt")
    assert {"pymupdf", "rapidocr", "onnxruntime", "pytest"} <= pkgs  # the parser reads the pins
    assert not sorted(p for p in pkgs if p not in low), "packages the README does not credit"
    for needed in ("PP-OCRv6", "ch_ppocr_mobile_v2.0_cls", "MODEL_LICENSES.md", "Apache-2.0", "AGPL-3.0", "Ollama", "Arial"):
        assert needed in doc, needed


def test_readme_quotes_the_capability_matrix():
    rows = load_capabilities()["capabilities"]
    table = matrix_markdown()
    assert between(text(README), "capabilities") == table, STALE
    assert len(table.splitlines()) == len(rows) + 2  # a header, a rule and one line per capability
    assert all(f"| {r['name']} | {r['status']} | {len(r['evidence'])} |" in table for r in rows)


def test_matrix_text_cannot_break_the_table():
    data = {"capabilities": [{"name": "A | B", "status": "Planned", "evidence": [], "note": "one\ntwo | three"}],
            "limitations": ["a | b\nc"], "assumptions": []}
    assert matrix_markdown(data).splitlines()[2:] == [r"| A \| B | Planned | 0 | one two \| three |"]
    assert "a \\| b c" in limitations_markdown(data)


def block(name: str, body: str) -> str:
    return f"<!-- {name}:start -->\n{body}\n<!-- {name}:end -->"


def test_refresh_rewrites_the_generated_blocks_and_nothing_else(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text(f"intro\n{block('capabilities', 'OLD')}\nafter\n", encoding="utf-8")
    (tmp_path / "docs" / "limitations.md").write_text(f"{block('limitations', 'OLD')}\nend\n", encoding="utf-8")
    refresh(tmp_path)
    assert text(tmp_path / "README.md") == f"intro\n{block('capabilities', matrix_markdown())}\nafter\n"
    assert text(tmp_path / "docs" / "limitations.md") == f"{block('limitations', limitations_markdown())}\nend\n"
    once = text(tmp_path / "README.md")
    refresh(tmp_path)  # a second run changes nothing
    assert text(tmp_path / "README.md") == once


def test_refresh_refuses_a_file_without_its_block(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("no block here\n", encoding="utf-8")
    (tmp_path / "docs" / "limitations.md").write_text(block("limitations", "OLD"), encoding="utf-8")
    with pytest.raises(ValueError, match=r"README.md needs one <!-- capabilities:start -->"):
        refresh(tmp_path)
    assert text(tmp_path / "README.md") == "no block here\n"


def test_documents_make_no_verdicts():
    for doc in (README, ARCHITECTURE, LIMITATIONS):
        assert not VERDICT.search(text(doc)), (doc.name, VERDICT.search(text(doc)))


def test_limitations_document_quotes_the_limitations_and_assumptions():
    doc, caps = text(LIMITATIONS), load_capabilities()
    lists = limitations_markdown()
    assert between(doc, "limitations") == lists, STALE
    assert all(" ".join(s.split()).replace("|", "\\|") in lists for s in caps["limitations"] + caps["assumptions"])


def test_limitations_document_has_a_false_positive_row_for_every_detector():
    """Beyond the lists: which ordinary things raise which finding. A detector with wording of its own in the templates needs a row."""
    doc = text(LIMITATIONS)
    assert re.search(r"^#{2,} .*false positives", doc, re.I | re.M)  # a section of its own, not only the title
    detectors = {d for d, c in TEMPLATES if d != "*" and c != "processing_limitation"}  # a limitation is covered by the text under the table
    assert {"pdf_revisions", "cross_name", "signature"} <= detectors  # the set is read from the templates, so it must not be empty
    assert not sorted(d for d in detectors if f"`{d}`" not in doc), "add a row to the table of likely false positives for these detectors"


def test_readme_commands_parse_and_cover_the_cli():
    lines = re.findall(r"^\s*(?:\$ )?python -m docforensics (.+)$", text(README), re.M)
    assert {shlex.split(line)[0] for line in lines} == {"run", "trace", "verify-audit", "serve"}
    for line in lines:
        cli._parser().parse_args(shlex.split(line))  # an unknown flag or a missing argument exits


@pytest.mark.parametrize("doc", [README, ARCHITECTURE, LIMITATIONS], ids=lambda p: p.name)
def test_links_point_at_files_that_exist(doc):
    targets = re.findall(r"\]\(([^)\s]+)\)", text(doc))
    if doc is README:
        assert {"docs/architecture.md", "docs/limitations.md", "LICENSE"} <= set(targets)
    for target in targets:
        if re.match(r"[a-z]+:", target):
            continue  # an address on the internet: not checked, the tests run offline
        assert (doc.parent / target.partition("#")[0]).exists(), (doc.name, target)


def test_architecture_diagram_shows_every_stage():
    doc = text(ARCHITECTURE)
    (diagram,) = re.findall(r"```mermaid\n(.*?)```", doc, re.S)
    for stage in STAGE_ORDER:
        assert re.search(rf"\b{stage}\b", diagram), stage
    assert "audit" in diagram and "dossier" in diagram
