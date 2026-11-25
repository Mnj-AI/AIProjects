# PaddleOCR-VL Chat

A small FastAPI web app that turns uploaded images and PDFs into Markdown using a
PaddleOCR-VL model served by a vLLM inference server.

## Architecture

Two components:

| Component | What it is | Runs on |
|---|---|---|
| **ocr-chat** (this repo) | FastAPI web app: upload UI, PDF splitting (pypdfium2), result collation, downloads | CPU, tiny |
| **ocr-server** | vLLM serving `PaddlePaddle/PaddleOCR-VL-1.6` (OpenAI-compatible API) | NVIDIA GPU, ~1.7B weights |

The web app is a pure client of the inference server — point `OCR_SERVER_URL`
at any OpenAI-compatible endpoint that can run the model.

## Quick start (Docker Compose)

Prerequisites: Docker with the Compose plugin, NVIDIA driver, and the
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

```bash
docker compose -f docker/compose.yaml up -d --build
```

- First start downloads the model weights from Hugging Face (cached in the
  `hf-cache` volume) — allow several minutes.
- Open http://localhost:8000 — the status bar turns green once the OCR server
  is ready.

Or use the one-command installer on a Linux server:

```bash
./install.sh            # installs to /opt/ocr-chat
./install.sh /srv/ocr   # or a custom directory
```

## Bare-metal alternative

```bash
# 1. Start the inference server (GPU machine)
vllm serve PaddlePaddle/PaddleOCR-VL-1.6 \
  --port 8091 --trust-remote-code --max-model-len 8192

# 2. Run the web app (any machine that can reach it)
pip install .
python app.py
```

## Configuration

Copy `.env.example` to `.env` and adjust. Real environment variables always
take precedence over `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `OCR_SERVER_URL` | `http://localhost:8091/v1` | OpenAI-compatible base URL of the OCR server |
| `OCR_MODEL` | *(auto-detect)* | Model name; empty = first model from `/v1/models` |
| `OCR_DPI` | `200` | Render DPI for PDF pages |
| `OCR_TIMEOUT` | `3600` | Per-request timeout (seconds) |
| `HOST` | `0.0.0.0` | Bind address for the web app |
| `PORT` | `8000` | Port for the web app |
| `MAX_UPLOAD_MB` | `50` | Maximum upload size (MB) |
| `OUTPUT_RETENTION_DAYS` | `7` | Delete generated `.md` files older than N days (0 = keep) |
| `API_TOKEN` | *(empty)* | Shared secret; empty = auth disabled |
| `LOG_LEVEL` | `INFO` | Logging level |

### Optional API token

Set `API_TOKEN` to require a shared secret on `/api/ocr` and `/download/*`.
The UI has a token button (🔓/🔒) in the status bar; API clients send the
`X-API-Token` header (or `?token=` for downloads).

## API

- `GET /api/health` — `{ok, model}` (or `{ok: false, error}`)
- `POST /api/ocr` — multipart `file`; streams NDJSON `progress` / `error` / `result`
- `GET /download/{name}` — the generated Markdown file

## Repository layout

```
app.py               FastAPI application
static/              Frontend (index.html + vendored marked/DOMPurify)
docker/Dockerfile    Image for the web app
docker/compose.yaml  Full stack: vLLM OCR server + web app
install.sh           One-command Linux installer
docs/INSTALL.md      Deployment guide (incl. offline/air-gapped)
docs/OPERATIONS.md   Day-2 operations, security, troubleshooting
pyproject.toml       Pinned dependencies
```

## License

Apache License 2.0 — see [LICENSE](LICENSE). All runtime dependencies are
commercially safe (pypdfium2 Apache-2.0, Pillow BSD, marked MIT, DOMPurify
Apache-2.0). **Before commercial distribution, verify the license of the
PaddleOCR-VL model weights** you ship.
