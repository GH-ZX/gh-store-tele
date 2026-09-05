FROM python:3.12-slim AS builder

WORKDIR /bot
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY requirements.txt requirements-dev.txt* ./
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*
RUN uv pip install --no-cache --system --prefix=/install -r requirements.txt -r requirements-dev.txt

FROM python:3.12-slim

RUN groupadd -r botuser && useradd -r -g botuser -d /bot -s /sbin/nologin botuser

WORKDIR /bot
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=builder /install /usr/local
COPY . .
RUN chown -R botuser:botuser /bot
USER botuser
EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD ["python", "-u", "run.py"]