"""The capability matrix (design 9): what the tool does, partly does, plans and declines, kept in one JSON file next to this module.
The dossier prints it and the README quotes it; a status changes only when the evidence for it does."""
import json
import re
import sys
from pathlib import Path


def load_capabilities() -> dict:
    """{"capabilities": [{name, status, evidence, note}], "limitations": [...], "assumptions": [...]}"""
    return json.loads(Path(__file__).with_name("capabilities.json").read_text(encoding="utf-8"))


def _cell(s: str) -> str:
    """One line, with the character that would end a table cell escaped."""
    return " ".join(s.split()).replace("|", "\\|")


def matrix_markdown(data: dict | None = None) -> str:
    """The matrix as the README's table: capability, status, how many evidence entries back it (tests, and for four rows evaluation
    reports as well, as in the dossier's column), and the note."""
    rows = (data or load_capabilities())["capabilities"]
    return "\n".join(["| Capability | Status | Evidence | Note |", "|---|---|---|---|",
                      *(f"| {_cell(r['name'])} | {r['status']} | {len(r['evidence'])} | {_cell(r.get('note', ''))} |" for r in rows)])


def limitations_markdown(data: dict | None = None) -> str:
    """The limitations and the assumptions as two numbered lists, for docs/limitations.md."""
    d = data or load_capabilities()
    return "\n\n".join(f"### {title}\n\n" + "\n".join(f"{i}. {_cell(s)}" for i, s in enumerate(d[key], 1))
                       for title, key in (("Limitations", "limitations"), ("Assumptions", "assumptions")))


def refresh(root: Path) -> None:
    """Rebuild the two blocks the code writes: the matrix in README.md and the lists in docs/limitations.md. Each sits between
    <!-- name:start --> and <!-- name:end -->; a file without exactly one such block is refused, and nothing is written to it."""
    for rel, name, make in (("README.md", "capabilities", matrix_markdown), ("docs/limitations.md", "limitations", limitations_markdown)):
        path = root / rel
        new, n = re.subn(rf"(<!-- {name}:start -->\n).*?(\n<!-- {name}:end -->)", lambda m: m[1] + make() + m[2],
                         path.read_text(encoding="utf-8"), flags=re.S)
        if n != 1:
            raise ValueError(f"{rel} needs one <!-- {name}:start --> ... <!-- {name}:end --> block")
        path.write_bytes(new.encode("utf-8"))  # LF, as git keeps it


if __name__ == "__main__":  # from the repository folder: python -m docforensics.capabilities --update
    if sys.argv[1:] == ["--update"]:
        refresh(Path.cwd())
    else:
        print(matrix_markdown())
