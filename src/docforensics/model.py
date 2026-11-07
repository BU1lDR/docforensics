"""Data model (design 7.2). Coordinates are pixels of the page rendered at `Page.dpi`."""
from typing import Literal

from pydantic import BaseModel, ConfigDict

Box = tuple[float, float, float, float]  # x0, y0, x1, y1

FClass = Literal["observation", "inconsistency", "potential_manipulation", "processing_limitation"]
Family = Literal["visual", "arithmetic", "cross_document", "metadata", "limitation", "cluster"]
Status = Literal["open", "needs_verification", "confirmed_by_reviewer", "dismissed"]


class _Base(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")


class Word(_Base):
    id: str
    text: str
    box: Box
    conf: float = 1.0
    font: str | None = None
    size: float | None = None
    color: str | None = None
    pt_box: Box | None = None  # text-layer words: the PDF-point box as well


class Page(_Base):
    n: int  # 1-based
    width: int
    height: int
    dpi: int = 200
    image_path: str = ""  # relative to the case directory
    read_mode: Literal["text-layer", "ocr"] = "text-layer"
    quality_class: Literal["text-layer", "good", "degraded", "poor"] = "text-layer"
    sharpness: float | None = None
    words: list[Word] = []
    blobs: list[Box] = []  # non-text ink: stamp and signature candidates
    upside_down: tuple[int, int] | None = None  # (items upside down, items counted) when most are: the page was scanned or stored half a turn


MODEL_READ_LABEL = "model-read (inference)"  # how a field the local model chose is marked in the note, the dossier and the page


class Field(_Base):
    id: str
    doc: str
    name: str
    raw: str
    value: str | None  # normalised: amounts "52000.00", dates ISO
    kind: Literal["amount", "date", "text", "id"]
    conf: float
    word_ids: list[str] = []
    page: int
    box: Box
    row: int | None = None  # table cells
    role: str = ""  # "name" | "address" | "employer" | "account": set from the type spec
    note: str = ""
    model_read: bool = False  # chosen and named by the local model on a page of a type without a spec: inference, not a rule's reading


class Evidence(_Base):
    doc: str
    page: int
    box: Box
    note: str = ""
    field_id: str | None = None
    value: str | None = None
    crop_path: str | None = None


class Finding(_Base):
    id: str = ""
    fclass: FClass
    detector: str
    family: Family
    title: str
    detail: str = ""
    conf: float = 1.0
    review_priority: int = 0
    evidence: list[Evidence] = []
    related: list[str] = []
    cluster: str | None = None
    explanation: str = ""
    explanation_source: Literal["template", "llm"] = "template"
    next_steps: list[str] = []
    status: Status = "open"
    note: str = ""


class Document(_Base):
    id: str
    sha256: str
    filename: str
    stored_path: str  # relative to the case directory
    size: int = 0
    kind: Literal["pdf-digital", "pdf-scanned", "image", "unknown"] = "unknown"
    doc_type: str = "unknown"
    type_conf: float = 0.0
    pages: list[Page] = []
    fields: list[Field] = []
    meta: dict[str, str] = {}


class Relation(_Base):
    a: str  # finding ids
    b: str
    kind: str
    reason: str


class Reasoning(_Base):
    """A local model's reading of a whole case, after the guard: inference, kept apart from what the detectors found."""
    source: Literal["llm"] = "llm"
    model: str = ""
    summary: str = ""
    relations: list[Relation] = []
    order: list[str] = []  # every finding of the case once, in the order a reviewer could read them
    rejected: list[tuple[str, str]] = []  # what the guard dropped, and why


class Case(_Base):
    id: str
    created: str  # UTC ISO
    documents: list[Document] = []
    findings: list[Finding] = []
    reasoning: Reasoning | None = None


class AuditEvent(_Base):
    seq: int
    ts: str
    actor: Literal["system", "reviewer"]
    event: str
    data: dict
    prev_hash: str
    hash: str
