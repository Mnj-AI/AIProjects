# PaddleOCR-VL Chat — lightweight FastAPI web app (CPU-only).
# The heavy OCR inference runs in a separate vLLM container (see compose.yaml).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY app.py ./
RUN pip install .

# Frontend (self-contained: no CDN dependencies).
COPY static/ ./static/

# Run as a non-root user.
RUN useradd --create-home --shell /usr/sbin/nologin ocrchat \
    && mkdir -p /app/output \
    && chown -R ocrchat:ocrchat /app
USER ocrchat

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
