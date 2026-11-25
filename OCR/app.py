"""Chat backend for a local PaddleOCR-VL 1.6 server.

Flow:
  1. The chat UI uploads an image or PDF to POST /api/ocr.
  2. Images are sent straight to the OCR server.
  3. PDFs are split page-by-page with pypdfium2 (rendered at OCR_DPI) and
     sent to the OCR server sequentially.
  4. Per-page markdown is collated into one document, saved under
     output/, and streamed back to the UI as NDJSON (progress + result).

The OCR server is expected to be an OpenAI-compatible vLLM server serving
PaddleOCR-VL 1.6, e.g. at http://localhost:8091/v1.
"""

import base64
import io
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import pypdfium2
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def _load_dotenv() -> None:
    """Minimal .env loader (real environment variables take precedence)."""
    env_file = BASE_DIR / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()

OCR_SERVER_URL = os.getenv("OCR_SERVER_URL", "http://localhost:8091/v1").rstrip("/")
OCR_MODEL = os.getenv("OCR_MODEL", "").strip()
OCR_DPI = int(os.getenv("OCR_DPI", "200"))
OCR_TIMEOUT = float(os.getenv("OCR_TIMEOUT", "3600"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
OUTPUT_RETENTION_DAYS = int(os.getenv("OUTPUT_RETENTION_DAYS", "7"))
API_TOKEN = os.getenv("API_TOKEN", "").strip()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ocr-chat")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
PDF_EXTENSIONS = {".pdf"}
MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

app = FastAPI(title="PaddleOCR-VL Chat")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# OpenAI-compatible client pointing at the local vLLM server.
client = OpenAI(
    api_key="EMPTY",
    base_url=OCR_SERVER_URL,
    timeout=OCR_TIMEOUT,
    max_retries=0,
)

_model_cache: Optional[str] = None


# ---------------------------------------------------------------------------
# Security and housekeeping
# ---------------------------------------------------------------------------

def require_token(
    x_api_token: str = Header(default="", alias="X-API-Token"),
    token: str = Query(default=""),
) -> None:
    """Optional shared-secret auth; enforced only when API_TOKEN is set."""
    if API_TOKEN and token != API_TOKEN and x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


def cleanup_old_outputs() -> int:
    """Delete OCR outputs older than OUTPUT_RETENTION_DAYS; return count."""
    if OUTPUT_RETENTION_DAYS <= 0:
        return 0
    cutoff = time.time() - OUTPUT_RETENTION_DAYS * 86400
    removed = 0
    for path in OUTPUT_DIR.iterdir():
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    if removed:
        logger.info(
            "Removed %d output file(s) older than %d day(s)",
            removed, OUTPUT_RETENTION_DAYS,
        )
    return removed


cleanup_old_outputs()


# ---------------------------------------------------------------------------
# OCR helpers
# ---------------------------------------------------------------------------

def get_model_name() -> str:
    """Return the configured model name, or auto-detect it from /models."""
    global _model_cache
    if OCR_MODEL:
        return OCR_MODEL
    if _model_cache:
        return _model_cache
    models = client.models.list()
    if not models.data:
        raise RuntimeError("OCR server returned no models")
    _model_cache = models.data[0].id
    return _model_cache


def ocr_image_bytes(image_bytes: bytes, mime: str = "image/png") -> str:
    """Send one image to the OCR server and return the markdown text."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_uri = f"data:{mime};base64,{b64}"
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": "OCR:"},
                ],
            }
        ],
        temperature=0.0,
    )
    return (response.choices[0].message.content or "").strip()


def sanitize_filename(name: str) -> str:
    """Reduce a user-supplied filename to a safe basename."""
    name = Path(name).name
    name = re.sub(r"[^\w.\-]+", "_", name).strip("._")
    return name or "upload"


def collate_markdown(filename: str, pages) -> str:
    """Join per-page markdown into one document."""
    sections = [f"# {filename}"]
    for page_no, text in pages:
        body = text.strip() or "_(no text detected)_"
        sections.append(f"<!-- page {page_no} -->\n\n{body}")
    return "\n\n---\n\n".join(sections) + "\n"


def ndjson(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    """Report whether the OCR server is reachable and which model it serves.

    Intentionally omits the server URL and exception details so this
    unauthenticated endpoint does not leak internal topology to the internet.
    """
    try:
        model = get_model_name()
        return {"ok": True, "model": model}
    except Exception:  # noqa: BLE001 - don't leak server details to the UI
        return {"ok": False, "error": "OCR server unreachable"}


@app.post("/api/ocr", dependencies=[Depends(require_token)])
async def api_ocr(file: UploadFile = File(...)):
    """OCR an uploaded image or PDF; stream NDJSON progress + result."""
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_MB} MB upload limit",
        )

    if ext in PDF_EXTENSIONS or data[:5] == b"%PDF-":
        kind = "pdf"
    elif ext in IMAGE_EXTENSIONS:
        kind = "image"
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext or 'unknown'}'. "
                "Send an image (png/jpg/webp/bmp) or a PDF."
            ),
        )

    logger.info("OCR request: %s (%s, %d bytes)", filename, kind, len(data))

    def generate():
        # Fail fast with a clear message if the OCR server is down.
        try:
            get_model_name()
        except Exception as exc:  # noqa: BLE001
            yield ndjson({
                "type": "error",
                "message": f"Cannot reach the OCR server: {exc}",
            })
            return

        pages = []
        current_page = 0
        try:
            if kind == "image":
                current_page = 1
                yield ndjson({
                    "type": "progress", "page": 1, "total": 1,
                    "status": "Sending image to OCR server…",
                })
                pages.append((1, ocr_image_bytes(data, MIME_BY_EXT[ext])))
            else:
                doc = pypdfium2.PdfDocument(data)
                try:
                    total = len(doc)
                    if total == 0:
                        yield ndjson({"type": "error", "message": "PDF has no pages"})
                        return
                    scale = OCR_DPI / 72.0
                    for page_no in range(total):
                        current_page = page_no + 1
                        yield ndjson({
                            "type": "progress",
                            "page": current_page,
                            "total": total,
                            "status": f"OCR page {current_page}/{total}…",
                        })
                        bitmap = doc[page_no].render(scale=scale)
                        buf = io.BytesIO()
                        bitmap.to_pil().save(buf, format="PNG")
                        pages.append((current_page, ocr_image_bytes(buf.getvalue())))
                finally:
                    doc.close()
        except Exception as exc:  # noqa: BLE001
            where = f" on page {current_page}" if current_page else ""
            yield ndjson({"type": "error", "message": f"OCR failed{where}: {exc}"})
            return

        markdown = collate_markdown(filename, pages)
        out_name = f"{int(time.time())}_{sanitize_filename(filename)}"
        (OUTPUT_DIR / out_name).write_text(markdown, encoding="utf-8")
        logger.info("Saved %s (%d page(s))", out_name, len(pages))
        yield ndjson({
            "type": "result",
            "markdown": markdown,
            "filename": filename,
            "kind": kind,
            "page_count": len(pages),
            "download_url": f"/download/{out_name}",
        })

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.get("/download/{name}", dependencies=[Depends(require_token)])
def download(name: str):
    safe = sanitize_filename(name)
    path = OUTPUT_DIR / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Download not found")
    return FileResponse(path, filename=safe, media_type="text/markdown")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=HOST, port=PORT)
