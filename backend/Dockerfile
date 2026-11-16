FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SPACESCAN_DB_PATH=/app/storage/spacescan.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY db ./db
COPY models ./models

RUN pip install --no-cache-dir . \
    && mkdir -p /app/storage/audio

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/api/v1/health || exit 1

CMD ["sh", "-c", "python -m db.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 1"]
