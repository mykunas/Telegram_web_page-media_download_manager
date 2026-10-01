FROM python:3.11-slim

ARG PUID=1000
ARG PGID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Keep dependency installation in a stable layer shared by backend and worker.
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

RUN groupadd --gid "${PGID}" --non-unique app \
    && useradd --uid "${PUID}" --gid "${PGID}" --non-unique --create-home --shell /usr/sbin/nologin app \
    && install -d -o app -g app /app/backend /app/worker /app/data /app/session /app/downloads /app/logs \
    && ln -s /app/downloads /downloads

COPY --chown=app:app backend/app /app/backend/app
COPY --chown=app:app app /app/worker

USER app
STOPSIGNAL SIGTERM

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
