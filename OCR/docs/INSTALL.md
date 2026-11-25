# Installation Guide

PaddleOCR-VL Chat is a two-component system:

| Component | What it does | Requirements |
|---|---|---|
| **ocr-server** | vLLM serving the PaddleOCR-VL 1.6 model (OpenAI-compatible API on port 8091) | NVIDIA GPU with CUDA, ~10 GB+ VRAM, Docker + NVIDIA Container Toolkit |
| **ocr-chat** | FastAPI web app (upload, progress, markdown download) on port 8000 | CPU only, Docker |

## 1. Server prerequisites

- Linux x86_64 with Docker Engine and the Docker Compose plugin.
- NVIDIA GPU with a current driver (`nvidia-smi` must work).
- NVIDIA Container Toolkit installed and verified:
  `docker run --rm --gpus all nvidia/cuda:12.4.1-base nvidia-smi`
- Internet access on first start (model weights ~several GB are pulled from
  Hugging Face and cached in the `hf-cache` volume).

## 2. Quick start (Docker Compose)

```bash
# from the project root
docker compose -f docker/compose.yaml up -d --build
```

First start takes several minutes (model download + load). Watch progress:

```bash
docker compose -f docker/compose.yaml logs -f ocr-server
```

When `ocr-server` is healthy, `ocr-chat` starts automatically.
Open **http://<server>:8000** — the status bar turns green when the OCR
server answers.

### One-command installer (Linux)

```bash
./install.sh            # installs to /opt/ocr-chat
./install.sh /srv/ocr   # or a custom target directory
```

## 3. Bare-metal (no Docker)

### OCR server (GPU machine)

```bash
pip install vllm
vllm serve PaddlePaddle/PaddleOCR-VL-1.6 \
    --port 8091 --trust-remote-code --max-model-len 8192
```

### Web app (any machine that can reach the OCR server)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on Linux
pip install .
python app.py                 # or: uvicorn app:app --host 0.0.0.0 --port 8000
```

Set `OCR_SERVER_URL` to the OCR server's address (see `.env.example`).

## 4. Configuration

All settings are environment variables (or a `.env` file next to `app.py`).
See `.env.example` for the full list:

| Variable | Default | Purpose |
|---|---|---|
| `OCR_SERVER_URL` | `http://localhost:8091/v1` | vLLM endpoint (OpenAI-compatible) |
| `OCR_MODEL` | *(auto-detect)* | Model id; leave empty to auto-detect |
| `OCR_DPI` | `200` | PDF render resolution |
| `OCR_TIMEOUT` | `3600` | Per-request timeout (seconds) |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Web app bind address |
| `MAX_UPLOAD_MB` | `50` | Upload size limit |
| `OUTPUT_RETENTION_DAYS` | `7` | Auto-delete old outputs (0 = keep forever) |
| `API_TOKEN` | *(empty = off)* | Shared secret; clients send `X-API-Token` header or `?token=` |
| `LOG_LEVEL` | `INFO` | Logging level |

## 5. Offline / air-gapped deployment

1. On a connected machine, download the model:
   `huggingface-cli download PaddlePaddle/PaddleOCR-VL-1.6`
2. Copy the cache directory into the `hf-cache` volume (or set
   `HF_HOME`/`HF_HUB_OFFLINE=1` in the compose file).
3. Build the web-app image on the connected machine and transfer it:
   `docker save ocr-chat | gzip > ocr-chat.tar.gz`
   `docker load < ocr-chat.tar.gz`

## 6. License notes

- This application is licensed under **Apache-2.0** (see `LICENSE`).
- All runtime dependencies are commercially safe: FastAPI/Starlette
  (BSD), uvicorn (BSD), OpenAI client (Apache-2.0), pypdfium2 (Apache-2.0),
  Pillow (BSD), marked (MIT), DOMPurify (Apache-2.0/MPL-2.0).
- **Model weights**: the PaddleOCR-VL 1.6 weights are distributed by
  PaddlePaddle on Hugging Face. **Review the model's license terms before
  commercial distribution** — model licenses are separate from this
  application's license.
