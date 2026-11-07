"""Document types are data (design 7.3): one TOML file per type in specs/, plus any in a directory the user adds."""
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

_BUILTIN = Path(__file__).parent / "specs"


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldSpec(_Spec):
    name: str
    kind: Literal["amount", "date", "text", "id"]
    labels: list[str] = []
    colon_labels: list[str] = []  # labels too common to stand alone ('Date'): they count only with a colon after them
    position: Literal["right", "below", "title"] = "right"  # where the value sits; "title" has no label: the tallest line of page 1 that is not a row of the form
    role: str = ""  # "name" | "address" | "employer" | "account": what cross-document checks compare
    index: int = 0  # for dates: which date in the value (a period holds two)
    lines: int = 1  # lines the value may wrap over (an address: 4); the lines under the first that start where it starts are part of it
    signed: bool = False  # an amount marked Dr is minus (a balance in overdraft); where the marker only names the column it is no sign


class ColumnSpec(_Spec):
    name: str
    kind: Literal["amount", "date", "text", "id"]
    headers: list[str]  # the heading as printed, in the wordings this type is known to use
    shared: list[str] = []  # wordings that another column prints too ('Amount' over the earnings and over the deductions): they name
    after: str = ""  # this column only as the heading right after the heading of the column `after` names
    anchor: bool = False  # a line that reads in this column is a row too, not only one that reads in the first column
    signed: bool = False  # an amount marked Dr is minus (a balance in overdraft); where the marker only names the column it is no sign

    @model_validator(mode="after")
    def _shared_goes_with_after(self) -> "ColumnSpec":
        if bool(self.shared) != bool(self.after):
            raise ValueError(f"column {self.name}: `shared` and `after` go together")
        return self


class MarkedSpec(_Spec):
    """A statement that prints one column of amounts and, beside it, a column that marks each amount Dr or Cr, in place of a debit
    column and a credit column. Looked for only when the heading names neither of those."""
    amount: list[str]  # the heading of the column of amounts, in the wordings this type is known to use
    marker: list[str]  # ... of the column of marks
    debit: list[str]  # what the mark of a debit reads
    credit: list[str]  # ... of a credit


class TableSpec(_Spec):
    prefix: str = "txn"  # cells are fields named "<prefix>.<column>"
    columns: list[ColumnSpec]  # the first column anchors the rows: a line is a row if it reads there
    ends_at: list[str] = []  # names of fields whose labels (gross_earnings) end the table: the first line that holds one is below its rows
    marked: MarkedSpec | None = None  # fills in the columns debit and credit, so the table needs both

    @model_validator(mode="after")
    def _marked_fills_debit_and_credit(self) -> "TableSpec":
        if self.marked and not {"debit", "credit"} <= {c.name for c in self.columns}:
            raise ValueError("`marked` fills in the columns debit and credit: the table needs both")
        return self


class TypeSpec(_Spec):
    type: str
    min_score: float  # keyword weight page 1 needs for the type to be chosen
    keywords: dict[str, float]  # a key may name several wordings of one thing, 'payslip|pay slip': the weight counts once
    fields: list[FieldSpec]
    table: TableSpec | None = None
    signature: list[str] = []  # captions printed under the signature, in the wordings this type is known to use; none: not looked for
    logo: bool = False  # a logo is printed right of the issuer's name; False: not looked for
    stamp: list[str] = []  # captions printed under the stamp, in the wordings this type is known to use; none: not looked for


def load_specs(extra_dir: Path | str | None = None) -> dict[str, TypeSpec]:
    """Type name to spec. A file that does not parse is an error that names the file; a spec in extra_dir replaces a
    built-in one of the same type."""
    out: dict[str, TypeSpec] = {}
    for folder in (_BUILTIN, Path(extra_dir) if extra_dir else None):
        for path in sorted(folder.glob("*.toml")) if folder else ():
            try:
                spec = TypeSpec.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
            except ValueError as e:  # TOML syntax, encoding and schema errors are all ValueErrors
                raise ValueError(f"{path.name}: {e}") from e
            out[spec.type] = spec
    return out
