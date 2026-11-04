"""Thresholds live in one place (design 7.4); every finding prints the ones it used."""
import tomllib
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class Thresholds:
    # starting values from the design; tuned on the dev split only
    low_conf: float = 0.6
    amount_abs: float = 1.0           # amounts match within 1 rupee ...
    amount_rel: float = 0.005         # ... or 0.5 %
    name_sim: float = 0.85
    label_sim: float = 0.86           # fuzzy label match; "closing balance" vs "opening balance" scores 0.8, so they stay apart
    income_rel: float = 0.05
    emi_ratio_max: float = 0.5
    max_doc_age_days: int = 90
    text_sim: float = 0.8             # an address or employer written twice matches when the text is at least this alike
    same_tool_minutes: int = 10       # documents of different kinds made by the same software this close together are noted
    # limits (design 7.10)
    max_file_bytes: int = 10_000_000
    max_pages: int = 20
    max_docs: int = 10
    stage_timeout_s: float = 120.0
    max_revisions: int = 16           # revisions of one PDF that are opened and compared
    max_revision_runs: int = 12       # changed runs listed one by one between two revisions; more is one finding
    max_diff_words: int = 5000        # words on a page, in either revision, that are compared
    # page-quality classes for OCR pages (docs/spike.md; refit on the dev split)
    sharp_good: float = 0.24
    sharp_poor: float = 0.18
    rel_good: float = 0.95
    rel_degraded: float = 0.5
    rel_poor: float = 0.2

    @classmethod
    def from_toml(cls, path: Path | str) -> "Thresholds":
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"unknown threshold(s): {', '.join(sorted(unknown))}")
        return cls(**data)

    def as_dict(self) -> dict:
        return asdict(self)
