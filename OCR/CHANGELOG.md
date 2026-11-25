# Changelog

All notable changes to PaddleOCR-VL Chat.

## 1.0.0 — 2026-02-13

### Added
- Docker Compose deployment (`docker/compose.yaml`) with a vLLM OCR server
  and the FastAPI web app as separate services.
- Dockerfile for the web app (`docker/Dockerfile`): non-root user,
  healthcheck, pinned dependencies.
- Optional shared-secret API token (`API_TOKEN` env var; `X-API-Token`
  header or `?token=` query param). Frontend has a token button that
  stores the token in browser localStorage.
- Configurable host/port (`HOST`, `PORT`), upload size limit
  (`MAX_UPLOAD_MB`), output retention cleanup (`OUTPUT_RETENTION_DAYS`),
  and structured logging (`LOG_LEVEL`).
- `pyproject.toml` with pinned dependencies (replaces `requirements.txt`).
- Vendored frontend scripts (`static/vendor/`) — no CDN dependencies.
- `install.sh` one-command installer for Linux servers.
- `docs/INSTALL.md` and `docs/OPERATIONS.md`.

### Changed
- PDF rendering switched from PyMuPDF (AGPL-3.0) to pypdfium2 (Apache-2.0)
  + Pillow (BSD) to keep the product commercially license-safe.
