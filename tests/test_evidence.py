"""Evidence crops (design 7.8): a padded cut of the page with the cited box outlined, one file per piece of evidence."""
from PIL import Image

from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.evidence import MAX_CROPS, OUTLINE, PAD, crop_evidence
from docforensics.findings import add_findings, doc_evidence
from docforensics.ingest import create_case
from docforensics.model import Evidence, Finding
from docforensics.pipeline import Ctx, run_case
from docforensics.read import read_stage
from tests.helpers import STATEMENT_LINES, lines_pdf

TH = Thresholds()
WHITE = (255, 255, 255)


def read_case(tmp_path):
    """A case whose one page is read: digital, 200 DPI, the small statement in its top third and white below it."""
    _, cd, _ = create_case(tmp_path, [("s.pdf", lines_pdf(STATEMENT_LINES))], TH)
    case = run_case(cd, TH, stages={"read": read_stage})
    return case, Ctx(cd, AuditLog(cd.audit_path), TH)


def cite(*boxes, page=1, doc="D1"):
    return Finding(fclass="observation", detector="t", family="visual", title="t",
                   evidence=[Evidence(doc=doc, page=page, box=b, note=f"n{i}") for i, b in enumerate(boxes, 1)])


def crop_of(ctx, e):
    return Image.open(ctx.cd.root / e.crop_path).convert("RGB")


def test_crop_is_padded_and_the_box_is_outlined(tmp_path):
    case, ctx = read_case(tmp_path)
    (f,) = add_findings(case, ctx, [cite((400.0, 1500.0, 600.0, 1540.0))])
    crop_evidence(case, ctx)
    e = f.evidence[0]
    assert e.crop_path == "crops/F-001-1.png"
    im = crop_of(ctx, e)
    assert im.size == (200 + 2 * PAD, 40 + 2 * PAD)
    assert im.getpixel((1, 1)) == WHITE and im.getpixel((im.width - 2, im.height - 2)) == WHITE  # the padding is the page, untouched
    assert im.getpixel((PAD + 1, PAD + 20)) == OUTLINE and im.getpixel((PAD + 199, PAD + 20)) == OUTLINE  # left and right edges
    assert im.getpixel((PAD + 100, PAD + 20)) == WHITE  # the inside of the box is not covered


def test_crop_is_clamped_at_the_page_edge(tmp_path):
    case, ctx = read_case(tmp_path)
    (f,) = add_findings(case, ctx, [cite((0.0, 1500.0, 100.0, 1530.0))])
    crop_evidence(case, ctx)
    im = crop_of(ctx, f.evidence[0])
    assert im.size == (100 + PAD, 30 + 2 * PAD) and im.getpixel((1, PAD + 15)) == OUTLINE


def test_crops_per_finding_are_capped(tmp_path):
    case, ctx = read_case(tmp_path)
    (f,) = add_findings(case, ctx, [cite(*[(10.0 + 30 * i, 1500.0, 30.0 + 30 * i, 1520.0) for i in range(MAX_CROPS + 3)])])
    crop_evidence(case, ctx)
    got = [e.crop_path for e in f.evidence]
    assert got == [f"crops/F-001-{i}.png" for i in range(1, MAX_CROPS + 1)] + [None] * 3
    assert len(list(ctx.cd.crops.glob("*.png"))) == MAX_CROPS


def test_whole_document_and_unusable_evidence_get_no_crop_and_the_rest_still_do(tmp_path):
    case, ctx = read_case(tmp_path)
    f = cite((50.0, 1500.0, 90.0, 1520.0), (9000.0, 9000.0, 9100.0, 9100.0))  # the second lies beyond the page
    f.evidence += [doc_evidence("D1"), Evidence(doc="D9", page=1, box=(1, 1, 50, 50)), Evidence(doc="D1", page=7, box=(1, 1, 50, 50))]
    (f,) = add_findings(case, ctx, [f])
    crop_evidence(case, ctx)
    assert [e.crop_path for e in f.evidence] == ["crops/F-001-1.png", None, None, None, None]
    failed = [e.data for e in ctx.audit.events() if e.event == "crop_failed"]
    assert [d["evidence"] for d in failed] == [2, 4, 5]  # a whole-document pointer is not a failure; the others are, and are logged
    assert all(d["finding"] == "F-001" and d["reason"] for d in failed)


def test_a_missing_page_image_loses_that_crop_not_the_stage(tmp_path):
    case, ctx = read_case(tmp_path)
    (f,) = add_findings(case, ctx, [cite((50.0, 1500.0, 90.0, 1520.0))])
    (ctx.cd.root / case.documents[0].pages[0].image_path).unlink()
    crop_evidence(case, ctx)
    assert f.evidence[0].crop_path is None
    (failed,) = [e.data for e in ctx.audit.events() if e.event == "crop_failed"]
    assert failed["evidence"] == 1
