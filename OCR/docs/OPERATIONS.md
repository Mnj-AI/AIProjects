# Operations Guide

Day-to-day operations for a deployed PaddleOCR-VL Chat instance.

## Status and logs

```bash
# Web app health (also shows OCR server reachability + model id)
curl http://localhost:8000/api/health

# Container status
docker compose -f docker/compose.yaml ps

# Live logs
docker compose -f docker/compose.yaml logs -f ocr-chat
docker compose -f docker/compose.yaml logs -f ocr-server
```

## Common operations

| Task | Command |
|---|---|
| Stop | `docker compose -f docker/compose.yaml down` |
| Start | `docker compose -f docker/compose.yaml up -d` |
| Rebuild web app after code changes | `docker compose -f docker/compose.yaml up -d --build ocr-chat` |
| Restart OCR server (model reload) | `docker compose -f docker/compose.yaml restart ocr-server` |
| Update model version | Change the image/command in `compose.yaml`, then `up -d ocr-server` |

## Security

- **API token**: set `API_TOKEN` in the compose file (or `.env`) to require
  a shared secret. Clients send it as the `X-API-Token` header (API calls)
  or `?token=` query parameter (download links). The web UI has a token
  button (🔒) that stores the token in the browser's localStorage.
- **TLS**: terminate TLS at a reverse proxy (nginx, Caddy, or a cloud LB)
  in front of port 8000. The app itself serves plain HTTP. Example with
  Caddy (auto-managed Let's Encrypt certificate):

  ```caddy
  # /etc/caddy/Caddyfile
  ocr.example.com {
      # Automatic HTTPS: Caddy provisions and renews a Let's Encrypt cert.
      # Requires ports 80/4443 reachable and DNS pointed at this host.

      # Optional: block direct access to the app's health endpoint from the
      # internet. It is unauthenticated by design (used by the container
      # healthcheck) and returns no secrets, but you may prefer to hide it.
      # handle /api/health { respond 404 }

      reverse_proxy 127.0.0.1:8000
  }
  ```

  Run Caddy on the same host as the stack (or a dedicated host that can
  reach `127.0.0.1:8000`). Point your domain's DNS at the host, then
  `systemctl restart caddy`. Verify with `curl https://ocr.example.com/api/health`.
  If you already use a cloud load balancer or nginx, apply the same idea:
  TLS termination in front of port 8000, and keep the vLLM port (8091)
  off the public internet entirely.
- **Upload limits**: `MAX_UPLOAD_MB` (default 50) rejects oversized files
  with HTTP 413.
- **Retention**: `OUTPUT_RETENTION_DAYS` (default 7) deletes generated
  markdown files older than the window at startup. Set `0` to disable.

## Backups

- **`hf-cache` volume** — model weights. Back up once; it is static.
- **`ocr-chat-output` volume** — generated markdown. Back up if customers
  need their results retained beyond the retention window.
- **`.env` / compose file** — configuration including `API_TOKEN`. Keep a
  copy outside the server.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Status bar red, "OCR server unreachable" | `ocr-server` still loading (first start takes minutes) or crashed — check its logs |
| `ocr-server` container exits immediately | GPU not visible: verify `docker run --rm --gpus all nvidia/cuda:12.4.1-base nvidia-smi`; check `nvidia-smi` for driver/VRAM |
| Out-of-memory on large PDFs | Lower `OCR_DPI` (e.g. 150) or raise `--max-model-len` only if needed |
| 401 from API | `API_TOKEN` is set but the client didn't send it (or sent the wrong one) |
| 413 on upload | File exceeds `MAX_UPLOAD_MB` |
| Slow first request after restart | vLLM warms up on the first inference; subsequent requests are faster |
| Model download fails (air-gapped) | See "Offline deployment" in `docs/INSTALL.md` |

## Upgrading

1. Stop the stack: `docker compose -f docker/compose.yaml down`
2. Copy the new release files over (or re-run `install.sh`).
3. `docker compose -f docker/compose.yaml up -d --build`
4. Verify: `curl http://localhost:8000/api/health`

Volumes (`hf-cache`, `ocr-chat-output`) persist across upgrades.
