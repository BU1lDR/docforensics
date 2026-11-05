"""Review app (design 7.8): FastAPI serving one static page. `serve` binds 127.0.0.1 only; every request is also checked for a loopback
Host (DNS rebinding) and, when it writes, for an Origin that matches (another site's page posting to this one). A case is analysed in a
background thread, one at a time (the OCR engine is shared). While it runs, case.json is replaced stage by stage and cannot safely be
read on Windows, so only its status is served; everything else waits (409) until the run ends. A name in a URL is validated before any
path is built from it."""
import re
import threading
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import UploadFile

from ..audit import AuditLog
from ..capabilities import load_capabilities
from ..config import Thresholds
from ..dossier import audit_view, build_dossier
from ..explain.llm import OllamaClient
from ..ingest import create_case
from ..model import Status
from ..pipeline import Ctx, run_case
from ..relations import build_relations
from ..review import MAX_NOTE, apply_review
from ..signing import checkpoint
from ..store import CaseDir, load_case

HOST = "127.0.0.1"
STATIC = Path(__file__).with_name("static")
ASSETS = {"app.js": "text/javascript", "style.css": "text/css"}  # fixed: a Windows registry entry can map .js to text/plain, which nosniff refuses
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
SLACK = 1 << 20  # multipart framing and file names, on top of the files themselves
DOC_ID = re.compile(r"D\d{1,3}")
CROP_NAME = re.compile(r"F-\d{3,}-\d{1,2}\.png")
INTERRUPTED = "interrupted: the analysis did not finish (the server may have stopped part-way), so these results are incomplete"


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status | None = None
    note: str | None = Field(None, max_length=MAX_NOTE)


def _parts(url: str):
    try:
        return urlsplit(url)
    except ValueError:
        return None


def create_app(data_root: Path | str, th: Thresholds | None = None, llm: OllamaClient | None = None) -> FastAPI:
    th = th or Thresholds()
    data_root = Path(data_root)
    app = FastAPI(title="docforensics review", docs_url=None, redoc_url=None, openapi_url=None)  # the docs page loads its code from a CDN
    jobs: dict[str, dict] = {}
    run_lock = threading.Lock()   # one analysis at a time
    edit_lock = threading.Lock()  # every read or write of case.json and the dossier files, so none meets a file being replaced

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host, origin = request.headers.get("host", ""), request.headers.get("origin")
        p = _parts("//" + host)
        if p is None or p.hostname not in LOOPBACK:
            return JSONResponse({"detail": "this app answers on the loopback address only"}, 403)
        if request.method not in ("GET", "HEAD") and origin is not None and ((o := _parts(origin)) is None or o.netloc != host):
            return JSONResponse({"detail": "cross-origin request refused"}, 403)
        resp = await call_next(request)
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    def open_case(case_id: str) -> CaseDir:
        try:
            return CaseDir.open(data_root, case_id)
        except (ValueError, FileNotFoundError):
            raise HTTPException(404, "no such case")

    def settled(case_id: str) -> CaseDir:
        cd = open_case(case_id)
        if jobs.get(case_id, {}).get("status") == "processing":
            raise HTTPException(409, "the case is still being processed")
        return cd

    def finished(cd: CaseDir) -> bool:
        """The last stage logs its end even when it fails, so that event says the run got to the finish."""
        try:
            return any(e.event == "stage_end" and e.data.get("stage") == "dossier" for e in AuditLog(cd.audit_path).events())
        except (ValueError, OSError):
            return False

    def work(cd: CaseDir) -> None:
        job = jobs[cd.id]
        with run_lock:
            try:
                run_case(cd, th, on_stage=lambda name: job.update(stage=name), llm=llm)
                jobs[cd.id] = {"status": "done", "stage": ""}
            except Exception as e:
                error = f"{type(e).__name__}: {e}"[:300]
                try:
                    AuditLog(cd.audit_path).append("system", "run_failed", {"error": error})
                    checkpoint(cd)
                except Exception:
                    pass  # the failure is reported to the browser either way
                jobs[cd.id] = {"status": "failed", "stage": "", "error": error}

    @app.post("/api/cases")
    async def upload(request: Request):
        try:
            size = int(request.headers.get("content-length", 0))
        except ValueError:
            size = 0
        cap = th.max_docs * th.max_file_bytes + SLACK
        if size > cap:
            raise HTTPException(413, f"upload too large: the limit is {th.max_docs} files of {th.max_file_bytes} bytes each ({cap} bytes in all)")
        form = await request.form()
        try:
            files = [f for f in form.getlist("files") if isinstance(f, UploadFile)]
            if not files:
                raise HTTPException(400, "no files in the upload: send them as multipart form fields named 'files'")
            named = [(f.filename or "unnamed", await f.read(th.max_file_bytes + 1)) for f in files]  # one byte over the limit is enough to refuse a file
        finally:
            await form.close()
        case, cd, _ = await run_in_threadpool(create_case, data_root, named, th)
        jobs[cd.id] = {"status": "processing", "stage": "queued", "intake": {
            "accepted": [{"id": d.id, "filename": d.filename, "size": d.size} for d in case.documents],
            "rejected": [f.detail for f in case.findings]}}  # at this point the only findings are the refusals
        threading.Thread(target=work, args=(cd,), daemon=True).start()
        return {"case_id": cd.id}

    @app.get("/api/cases/{case_id}")
    def case_status(case_id: str):
        cd = open_case(case_id)
        job = jobs.get(case_id)
        if job is None:  # a case from an earlier session: it was finished then, or it was cut short
            job = {"status": "done", "stage": ""} if finished(cd) else {"status": "failed", "stage": "", "error": INTERRUPTED}
        out = {"status": job["status"], "stage": job.get("stage", ""), "error": job.get("error"), "intake": job.get("intake"),
               "low_conf": th.low_conf, "case": None}
        if job["status"] != "processing":
            try:
                with edit_lock:
                    out["case"] = load_case(cd)
            except (ValueError, OSError) as e:
                out.update(status="failed", error=f"case.json cannot be read ({type(e).__name__})")
        return out

    @app.post("/api/cases/{case_id}/findings/{finding_id}/review")
    def review(case_id: str, finding_id: str, body: Review):
        cd = settled(case_id)
        with edit_lock:
            case = load_case(cd)
            try:
                return apply_review(case, Ctx(cd, AuditLog(cd.audit_path), th), finding_id, body.status, body.note)
            except KeyError:
                raise HTTPException(404, "no such finding")
            except ValueError as e:  # nothing was changed
                raise HTTPException(422, str(e))

    @app.get("/api/cases/{case_id}/pages/{doc}/{n:int}.png")
    def page(case_id: str, doc: str, n: int):
        cd = settled(case_id)
        if not DOC_ID.fullmatch(doc) or n < 1 or not (cd.pages / f"{doc}-p{n}.png").is_file():
            raise HTTPException(404, "no such page")
        return FileResponse(cd.pages / f"{doc}-p{n}.png", media_type="image/png")

    @app.get("/api/cases/{case_id}/crops/{name}")
    def crop(case_id: str, name: str):
        cd = settled(case_id)
        if not CROP_NAME.fullmatch(name) or not (cd.crops / name).is_file():
            raise HTTPException(404, "no such crop")
        return FileResponse(cd.crops / name, media_type="image/png")

    @app.get("/api/cases/{case_id}/audit")
    def audit(case_id: str):
        cd = settled(case_id)
        return audit_view(Ctx(cd, AuditLog(cd.audit_path), th))

    @app.get("/api/cases/{case_id}/relations")
    def relations(case_id: str):
        cd = settled(case_id)
        with edit_lock:
            case = load_case(cd)
        return build_relations(case, th)

    def dossier_download(case_id: str, kind: str) -> Response:
        """Built at the moment of the request, so it holds the reviewer's actions so far; each build is in the audit trail. The bytes are
        read inside the lock, before the next build can replace the file."""
        cd = settled(case_id)
        with edit_lock:
            html, js = build_dossier(load_case(cd), Ctx(cd, AuditLog(cd.audit_path), th))
            data = (html if kind == "html" else js).read_bytes()
        media = "text/html; charset=utf-8" if kind == "html" else "application/json"
        return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="dossier-{cd.id}.{kind}"'})

    @app.get("/api/cases/{case_id}/dossier")
    def dossier(case_id: str):
        return dossier_download(case_id, "html")

    @app.get("/api/cases/{case_id}/dossier.json")
    def dossier_json(case_id: str):
        return dossier_download(case_id, "json")

    @app.get("/api/capabilities")
    def capabilities():
        return load_capabilities()

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", media_type="text/html")

    @app.get("/static/{name}")
    def asset(name: str):
        if name not in ASSETS:
            raise HTTPException(404, "no such file")
        return FileResponse(STATIC / name, media_type=ASSETS[name])

    return app
