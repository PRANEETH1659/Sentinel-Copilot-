# Phase 5d - SentinelCopilot API (and its consumers) as a container image.
#
# Build:  docker build -t sentinelcopilot .
# Run:    docker compose --profile app up -d     (see docker-compose.yml)
#
# Ollama is NOT inside this image: it stays on your Windows host (GPU), and
# the container reaches it at http://host.docker.internal:11434.

FROM python:3.12-slim

# No .pyc files, and logs appear immediately instead of being buffered.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Requirements are copied BEFORE the code, so Docker reuses the cached
# "pip install" layer on every rebuild where only code changed.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ app/
COPY sample_docs/ sample_docs/
COPY sample_logs/ sample_logs/

# Never run as root inside the container.
RUN useradd --create-home --uid 1000 sentinel
USER sentinel

EXPOSE 8000

# Docker marks the container unhealthy if /health stops answering.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

# Default command = the API. The consumer services in docker-compose.yml
# reuse this same image and just override this command.
CMD ["uvicorn", "app.main_ph1:app", "--host", "0.0.0.0", "--port", "8000"]
