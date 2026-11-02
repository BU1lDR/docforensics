"""Case directory: data/cases/<id>/ holds files/, pages/, crops/, case.json and audit.jsonl. No database."""
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .model import Case

CASE_ID_RE = re.compile(r"C-\d{8}-\d{6}-[0-9a-f]{4}")


@dataclass(frozen=True)
class CaseDir:
    root: Path

    @property
    def id(self) -> str:
        return self.root.name

    files = property(lambda self: self.root / "files")
    pages = property(lambda self: self.root / "pages")
    crops = property(lambda self: self.root / "crops")
    case_json = property(lambda self: self.root / "case.json")
    audit_path = property(lambda self: self.root / "audit.jsonl")
    dossier_html = property(lambda self: self.root / "dossier.html")
    dossier_json = property(lambda self: self.root / "dossier.json")

    @classmethod
    def create(cls, data_root: Path | str) -> "CaseDir":
        now = datetime.now(timezone.utc)
        root = Path(data_root) / "cases" / f"C-{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        cd = cls(root)
        for d in (cd.files, cd.pages, cd.crops):
            d.mkdir(parents=True)
        return cd

    @classmethod
    def open(cls, data_root: Path | str, case_id: str) -> "CaseDir":
        if not CASE_ID_RE.fullmatch(case_id):
            raise ValueError(f"not a case id: {case_id!r}")
        root = Path(data_root) / "cases" / case_id
        if not root.is_dir():
            raise FileNotFoundError(case_id)
        return cls(root)


def save_case(case: Case, cd: CaseDir) -> None:
    tmp = cd.case_json.with_suffix(".json.tmp")
    tmp.write_text(case.model_dump_json(indent=1), encoding="utf-8")
    os.replace(tmp, cd.case_json)


def load_case(cd: CaseDir) -> Case:
    return Case.model_validate_json(cd.case_json.read_text(encoding="utf-8"))
