#!/usr/bin/env bash
# PaddleOCR-VL Chat — one-command installer for Linux servers.
# Usage: ./install.sh [target_dir]   (default target: /opt/ocr-chat)
set -euo pipefail

TARGET_DIR="${1:-/opt/ocr-chat}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> PaddleOCR-VL Chat installer"
echo "    source:  ${SRC_DIR}"
echo "    target:  ${TARGET_DIR}"

# --- Prerequisite checks -------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker not found. Install Docker Engine first." >&2
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: docker compose plugin not found." >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: cannot talk to the Docker daemon (permissions?)." >&2
    exit 1
fi
if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "WARNING: nvidia-smi not found. The OCR server needs an NVIDIA GPU" >&2
    echo "         with a working driver and the NVIDIA Container Toolkit." >&2
fi

# --- Copy project files ---------------------------------------------------
mkdir -p "$TARGET_DIR"
cp -r "$SRC_DIR"/app.py "$SRC_DIR"/pyproject.toml "$SRC_DIR"/README.md \
      "$SRC_DIR"/LICENSE "$SRC_DIR"/CHANGELOG.md "$SRC_DIR"/.env.example \
      "$SRC_DIR"/static "$SRC_DIR"/docker "$TARGET_DIR"/
echo "==> Files copied to ${TARGET_DIR}"

# --- Optional hardening config --------------------------------------------
ENV_FILE="$TARGET_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$TARGET_DIR/.env.example" "$ENV_FILE"
    echo "==> Created ${ENV_FILE} from .env.example"
    echo "    Review it before starting (API_TOKEN, MAX_UPLOAD_MB, ...)."
fi

# --- Build and start -------------------------------------------------------
cd "$TARGET_DIR"
docker compose -f docker/compose.yaml up -d --build
echo "==> Containers started. Waiting for the OCR server to load the model..."

# --- Wait for health -------------------------------------------------------
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
        echo "==> Ready: http://localhost:8000"
        exit 0
    fi
    sleep 10
done

echo "WARNING: web app not healthy after 10 minutes." >&2
echo "         Check logs: docker compose -f docker/compose.yaml logs -f" >&2
exit 1
