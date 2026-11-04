"""Document types are data (design 7.3): one TOML file per type in specs/, plus any in a directory the user adds."""
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

_BUILTIN = Path(__file__).parent / "specs"


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldSpec(_Spec):
    name: str
    kind: Literal["amount", "date", "text", "id"]
    labels: list[str] = []
    position: Literal["right", "below", "title"] = "right"  # where the value sits; "title" has no label: the page's tallest line
    role: str = ""  # "name" | "address" | "employer" | "account": what cross-document checks compare
    index: int = 0  # for dates: which date in the value (a period holds two)


class ColumnSpec(_Spec):
    name: str
    kind: Literal["amount", "date", "text", "id"]
    headers: list[str]  # the heading as printed, in the wordings this type is known to use


class TableSpec(_Spec):
    prefix: str = "txn"  # cells are fields named "<prefix>.<column>"
    columns: list[ColumnSpec]  # the first column anchors the rows: a line is a row if it reads there


class TypeSpec(_Spec):
    type: str
    min_score: float  # keyword weight page 1 needs for the type to be chosen
    keywords: dict[str, float]
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
