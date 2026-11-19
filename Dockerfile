# Nigehban backend for Hugging Face Spaces (Docker SDK) or any container host.
# Runtime data (about 140 MB) is downloaded at start from a private HF dataset:
#   NIGEHBAN_RUNTIME_DATA_REPO=<user>/nigehban-runtime and HF_TOKEN (read access).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=7860
RUN useradd -m -u 1000 user
WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY pipelines ./pipelines
COPY data/reference ./data/reference
RUN pip install --upgrade pip && pip install -e . && chown -R user:user /app

USER user
EXPOSE 7860
CMD ["python", "-m", "backend.app.start"]
