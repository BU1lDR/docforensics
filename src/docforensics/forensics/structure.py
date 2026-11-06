"""Raw file structure (Task 27, a cut-down 'hex-level' check): facts read from the stored bytes of a PDF, JPEG or PNG, whatever its
read mode. Bytes after the end of the file, an /Info record that disagrees with the XMP packet, a signature range that stops short of
the end, embedded files and action keys, a rebuilt index, an editor named in picture metadata. Each is one observation that points at
the whole document, with a byte offset or object number and at most 32 bytes shown. Anyone who can write the file can write all of
this, so none of it is a verdict. It does not check a signature's cryptography, does not open embedded files or run actions, and
does not look for malware."""
import io
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import pymupdf
from PIL import Image

from ..findings import doc_evidence, limitation, quote
from ..ingest import sniff
from ..model import Case, Document, Finding
from ..pipeline import Ctx
from .pdf_meta import _length, pdf_time

DETECTOR = "file_structure"
_WS = b" \t\r\n\x00\x0c"  # bytes that may follow the last marker of a file without being reported
_MAX_OBJECTS = 20_000  # objects of a PDF that are scanned for action keys and signatures
_MAX_PICTURES = 50  # JPEG pictures of a PDF that are followed to their end
_IMAGE_EDITORS = ("photoshop", "gimp", "lightroom", "paint.net", "pixlr", "krita", "affinity", "picsart", "snapseed", "canva",
                  "paint shop", "photopea", "illustrator", "inkscape")  # names of programs that edit pictures
_ACTION = re.compile(r"/(JavaScript|JS|OpenAction|AA|Launch)(?![^\s()<>\[\]{}/%])")  # whole names only
_JPEG_STREAM = re.compile(r"/Filter\s*(?:\[\s*)?/DCTDecode")  # ponytail: a picture with another filter in front of DCT is not looked at
_RANGE = re.compile(r"/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]")
_STRING, _HEX = re.compile(r"\((?:\\.|[^\\()])*\)", re.S), re.compile(r"<[0-9A-Fa-f\s]*>")
_MARKER = re.compile(rb"\xff[^\x00\xd0-\xd7\xff]")  # the next marker after JPEG data: not a stuffed zero, a restart marker or a fill byte
_XMP = {"{http://ns.adobe.com/pdf/1.3/}Producer": "Producer", "{http://ns.adobe.com/xap/1.0/}CreatorTool": "CreatorTool",
        "{http://ns.adobe.com/xap/1.0/}CreateDate": "CreateDate", "{http://ns.adobe.com/xap/1.0/}ModifyDate": "ModifyDate"}


def _obs(doc: Document, title: str, detail: str, note: str) -> Finding:
    return Finding(fclass="observation", detector=DETECTOR, family="metadata", title=title, detail=detail, evidence=[doc_evidence(doc.id, note)])


def _lim(doc: Document, title: str, detail: str) -> Finding:
    return limitation(DETECTOR, title, detail, [doc_evidence(doc.id, "file structure")])


def dump(b: bytes) -> str:
    """At most 32 bytes as hex, then as ASCII with every non-printable byte a dot. Printable ASCII only, whatever the bytes are."""
    b = b[:32]
    return f"{b.hex(' ')} | {''.join(chr(c) if 32 <= c < 127 else '.' for c in b)}"


def _after(doc: Document, data: bytes, end: int, title: str, what: str, unit: str = "file") -> list[Finding]:
    """An observation when anything but white space and zero bytes follows offset `end`, where the last marker of the file ends."""
    rest = data[end:]
    start = end + len(rest) - len(rest.lstrip(_WS))
    if start >= len(data):
        return []
    n = len(data) - start
    return [_obs(doc, title, f"{what} ends at byte offset {end}. {n} bytes begin at byte offset {start} (the first that is not white space), "
                             f"in a {unit} of {len(data)} bytes. The first {min(n, 32)} are: {dump(data[start:])}.", "bytes after the end marker")]


def _plain(source: str) -> str:
    """An object's source without its strings (they are data, not syntax) and with #-escapes in names undone."""
    for _ in range(4):  # strings nest: the innermost go first
        source, n = _STRING.subn(" ", source)
        if not n:
            break
    return re.sub(r"#([0-9A-Fa-f]{2})", lambda m: chr(int(m[1], 16)), _HEX.sub(" ", source))


def action_names(source: str) -> list[str]:
    """Which of /JavaScript /JS /OpenAction /AA /Launch an object's source names, sorted. Names only: never what they point to."""
    return sorted(set(_ACTION.findall(_plain(source))))


# --- PDF

def _object(pdf, container: int, key: str) -> str:
    """' (object N)' for the object that a key of `container` points at, or nothing."""
    kind, value = pdf.xref_get_key(container, key)
    m = re.match(r"(\d+) 0 R", value) if kind == "xref" else None
    return f" (object {m[1]})" if m else ""


def _xmp(packet: str) -> dict[str, str]:
    """Producer, CreatorTool, CreateDate and ModifyDate of an XMP packet, written as elements or as attributes. ValueError when the
    packet declares a document type or entities (no safe parser is installed, so it is not parsed) or is not XML."""
    if re.search(r"<!(?:DOCTYPE|ENTITY)", packet):
        raise ValueError("it declares a document type or entities")
    try:
        root = ET.fromstring(packet.encode("utf-8"))
    except ET.ParseError as e:
        raise ValueError(f"it could not be parsed ({e})") from e
    out: dict[str, str] = {}
    for el in root.iter():
        for key, value in [*el.attrib.items(), (el.tag, "".join(el.itertext()).strip())]:
            if key in _XMP and value.strip():
                out.setdefault(_XMP[key], value.strip())
    return out


def _iso(s: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)  # no zone means UTC, as for PDF dates


def _records(doc: Document, pdf) -> list[Finding]:
    packet = pdf.get_xml_metadata()
    if not packet:
        return []
    try:
        xmp = _xmp(packet)
    except ValueError as e:
        return [_lim(doc, "XMP packet not read", f"The XMP packet of this PDF was not compared with its /Info record: {e}.")]
    info, rows = pdf.metadata, []
    for label, key, xkey in (("producer", "producer", "Producer"), ("creator tool", "creator", "CreatorTool"),
                             ("creation date", "creationDate", "CreateDate"), ("modification date", "modDate", "ModifyDate")):
        a, b = " ".join((info.get(key) or "").split()), " ".join(xmp.get(xkey, "").split())
        if not a or not b:
            continue  # a value in one record only is not a disagreement
        if label.endswith("date"):
            x, y = pdf_time(a), _iso(b)
            if x is None or y is None or x.replace(microsecond=0) == y.replace(microsecond=0):  # ponytail: a date that does not parse is not compared
                continue
            rows.append(f"{label}: /Info {x.isoformat(sep=' ')}, XMP {y.isoformat(sep=' ')}")
        elif a != b:
            rows.append(f'{label}: /Info "{quote(a)}", XMP "{quote(b)}"')
    if not rows:
        return []
    where = f"/Info{_object(pdf, -1, 'Info')}, XMP{_object(pdf, pdf.pdf_catalog(), 'Metadata')}"
    return [_obs(doc, "The /Info record and the XMP packet disagree", f"The file's records state different values ({where}): " + "; ".join(rows) + ".",
                 "file metadata")]


def _objects(doc: Document, pdf, data: bytes) -> list[Finding]:
    """Action keys by name, embedded files by name and size, and signature ranges against the end of the file."""
    out, keys, ranges, pictures = [], {}, [], []
    n = pdf.xref_length() - 1
    for x in range(1, min(n, _MAX_OBJECTS) + 1):
        source = _plain(pdf.xref_object(x))
        for name in action_names(source):
            keys.setdefault(name, []).append(x)
        ranges += [tuple(map(int, m.groups())) for m in _RANGE.finditer(source)]
        if "/Image" in source and _JPEG_STREAM.search(source):
            pictures.append(x)
    if n > _MAX_OBJECTS:
        out.append(_lim(doc, "Only part of the PDF objects were scanned",
                        f"The file has {n} objects; the first {_MAX_OBJECTS} were scanned for action keys and signatures, the rest were not."))
    names = pdf.embfile_names()  # ponytail: file-attachment annotations are not listed, only the document's embedded-files tree
    if names:
        listed = ", ".join(f'"{quote(name, 60)}" ({pdf.embfile_info(name).get("size", "?")} bytes)' for name in names[:10])
        out.append(_obs(doc, "PDF carries an embedded file" if len(names) == 1 else f"PDF carries {len(names)} embedded files",
                        f"The file contains {len(names)} embedded file(s): {listed}. Their content was not opened.", "embedded files"))
    if keys:
        listed = ", ".join(f"/{k} (object {', '.join(map(str, v[:3]))}{', ...' if len(v) > 3 else ''})" for k, v in sorted(keys.items()))
        out.append(_obs(doc, "PDF carries action keys", f"The file names these action keys: {listed}. Only the key names were read; no script, "
                                                       f"target or action was opened, decoded or run.", "action keys"))
    return out + _pictures(doc, pdf, pictures) + _signatures(doc, ranges, data)


def _pictures(doc: Document, pdf, pictures: list[int]) -> list[Finding]:
    """The JPEG pictures a PDF stores as they are: bytes after the end-of-image marker of each (the first _MAX_PICTURES pictures)."""
    out, lost = [], 0
    if len(pictures) > _MAX_PICTURES:
        out.append(_lim(doc, "Only part of the pictures were checked",
                        f"The file holds {len(pictures)} JPEG pictures; the first {_MAX_PICTURES} were followed to their end-of-image marker, the rest were not."))
    for x in pictures[:_MAX_PICTURES]:
        raw = pdf.xref_stream_raw(x)
        end = jpeg_end(raw)
        if end is None:
            lost += 1
        else:
            out += _after(doc, raw, end, "Bytes follow the end of a picture inside the PDF",
                          f"The picture stored in object {x}, up to its end-of-image marker,", "stream")
    if lost:
        out.append(_lim(doc, "Bytes after the end of a picture not checked",
                        f"{lost} JPEG picture(s) in this PDF could not be followed to their end-of-image marker, so the bytes after it could not be examined."))
    return out


def _signatures(doc: Document, ranges: list[tuple[int, ...]], data: bytes) -> list[Finding]:
    if not ranges:
        return []
    out = [_lim(doc, "Signature present, not verified",
                f"The file holds {len(ranges)} signature dictionary(ies) with a /ByteRange. Whether a signature is valid, who made it and whether the "
                f"signed bytes are intact was not checked: this check compares byte positions only, does not check signature cryptography and does not "
                f"look for malware.")]
    size, trimmed = len(data), len(data.rstrip(_WS))
    for a, b, c, d in ranges:
        if c + d < trimmed:
            out.append(_obs(doc, "Content follows the signed byte range",
                            f"A /ByteRange [{a} {b} {c} {d}] ends at byte offset {c + d}; the file is {size} bytes long, so {size - (c + d)} bytes "
                            f"follow the range the signature covers.", "signature byte range"))
        elif c + d > size:
            out.append(_obs(doc, "The signed byte range runs past the end of the file",
                            f"A /ByteRange [{a} {b} {c} {d}] ends at byte offset {c + d}; the file is {size} bytes long, {c + d - size} bytes short of it.",
                            "signature byte range"))
    return out


def _pdf_tail(doc: Document, data: bytes) -> list[Finding]:
    eof = data.rfind(b"%%EOF")
    if eof < 0:
        return [_lim(doc, "Bytes after the end of the file not checked", "The file has no end-of-file marker (%%EOF), so the bytes after it could not be examined.")]
    return _after(doc, data, eof + 5, "Bytes follow the last end-of-file marker", "The last end-of-file marker (%%EOF)")


def _repaired(doc: Document, pdf, data: bytes) -> list[Finding]:
    if not pdf.is_repaired:
        return []
    return [_obs(doc, "The file's index had to be rebuilt to be read",
                 f"The PDF reader could not use the cross-reference table (the file's index of its objects) and rebuilt it by scanning the file, "
                 f"{len(data)} bytes. Truncated, edited or damaged files need this, and so do some files from ordinary programs.", "cross-reference table")]


# --- JPEG and PNG

def jpeg_end(data: bytes) -> int | None:
    """The offset just past the end-of-image marker, found by walking the segments (a thumbnail inside holds an FFD9 of its own),
    or None when the walk does not reach one."""
    i, n = 2, len(data)
    while i + 1 < n:
        if data[i] != 0xFF:
            return None
        m = data[i + 1]
        if m == 0xFF:  # a fill byte
            i += 1
        elif m == 0xD9:
            return i + 2
        elif m == 0x01 or 0xD0 <= m <= 0xD7:  # markers without a length
            i += 2
        elif i + 4 > n:
            return None
        else:
            i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
            if m == 0xDA:  # the entropy-coded data follows the scan header, up to the next real marker
                found = _MARKER.search(data, i)
                if not found:
                    return None
                i = found.start()
    return None


def png_end(data: bytes) -> int | None:
    """The offset just past the IEND chunk, found by walking the chunks, or None when the walk does not reach one."""
    i = 8
    while i + 12 <= len(data):
        n = int.from_bytes(data[i:i + 4], "big")
        if data[i + 4:i + 8] == b"IEND":
            return i + 12 + n if i + 12 + n <= len(data) else None
        i += 12 + n
    return None


def _text(v) -> str:
    return v.decode("latin-1") if isinstance(v, bytes) else str(v)


def _exif_time(s) -> datetime | None:
    try:
        return datetime.strptime(_text(s).strip(), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _image_tail(doc: Document, data: bytes, kind: str) -> list[Finding]:
    end = (jpeg_end if kind == "jpeg" else png_end)(data)
    marker = "end-of-image marker" if kind == "jpeg" else "IEND chunk"
    if end is None:
        return [_lim(doc, "Bytes after the end of the image not checked", f"The {kind.upper()} could not be followed to its {marker}, so the bytes after it could not be examined.")]
    return _after(doc, data, end, "Bytes follow the end of the image", f"The image data, up to its {marker},")


def _image_meta(doc: Document, img, kind: str, th) -> list[Finding]:
    out, named = [], []
    exif = img.getexif()
    sources = [("EXIF Software", exif.get(0x0131)), ("PNG Software", img.info.get("Software") if kind == "png" else None)]
    for key in ("xmp", "XML:com.adobe.xmp"):
        packet = img.info.get(key)
        if packet:
            try:
                sources.append(("XMP CreatorTool", _xmp(_text(packet)).get("CreatorTool")))
            except ValueError as e:
                out.append(_lim(doc, "XMP packet not read", f"The XMP packet of this image was not read: {e}."))
            break
    for label, value in sources:
        if value and any(re.search(rf"\b{re.escape(w)}", _text(value), re.I) for w in _IMAGE_EDITORS):
            named.append(f'{label} "{quote(_text(value))}"')
    if named:
        out.append(_obs(doc, "Image metadata names image-editing software",
                        f"The image states: {'; '.join(named)}. Programs of this kind are used to edit pictures and also to produce them, so the name "
                        f"alone does not show that the image was edited.", "image metadata"))
    taken, saved = _exif_time(exif.get_ifd(0x8769).get(0x9003)), _exif_time(exif.get(0x0132))
    if taken and saved and (gap := (saved - taken).total_seconds()) > th.mod_after_create_s:
        out.append(_obs(doc, "Image saved after it was taken",
                        f"The EXIF record gives the time taken (DateTimeOriginal) as {taken.isoformat(sep=' ')} and the time saved (DateTime) as "
                        f"{saved.isoformat(sep=' ')}, {_length(gap)} later ({gap:.0f} s). Gaps over {th.mod_after_create_s} s are reported.", "image metadata"))
    return out


# --- the detector

def _run(doc: Document, steps) -> list[Finding]:
    out = []
    for name, step in steps:
        try:
            out += step()
        except Exception as e:  # a malformed file is a limitation, not an error that costs the other checks
            out.append(_lim(doc, f"File structure: {name} not checked", f"The check stopped on this file ({type(e).__name__}); nothing is reported from it."))
    return out


def file_structure(case: Case, doc: Document, ctx: Ctx) -> list[Finding]:
    data = (ctx.cd.root / doc.stored_path).read_bytes()
    kind = sniff(data)
    if kind is None:
        return [_lim(doc, "File type not recognised", "The first bytes are not those of a PDF, JPEG or PNG file, so no file-structure check was made.")]
    try:
        if kind == "pdf":
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                return _run(doc, [("end of file", lambda: _pdf_tail(doc, data)), ("metadata records", lambda: _records(doc, pdf)),
                                  ("objects", lambda: _objects(doc, pdf, data)), ("index", lambda: _repaired(doc, pdf, data))])
        with Image.open(io.BytesIO(data)) as img:
            return _run(doc, [("end of image", lambda: _image_tail(doc, data, kind)), ("image metadata", lambda: _image_meta(doc, img, kind, ctx.th))])
    except Exception as e:
        return [_lim(doc, "File structure not read", f"The file could not be opened as a {kind.upper()} ({type(e).__name__}), so no file-structure check was made.")]
