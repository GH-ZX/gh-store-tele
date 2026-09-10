FROM python:3.12-slim AS builder

WORKDIR /bot
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY requirements.txt requirements-dev.txt* ./
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*
RUN uv pip install --no-cache --system --prefix=/install -r requirements.txt -r requirements-dev.txt

FROM python:3.12-slim

# Copy official cloudflared binary into runtime image
COPY --from=cloudflare/cloudflared:latest /usr/local/bin/cloudflared /usr/local/bin/cloudflared

RUN groupadd -r botuser && useradd -r -g botuser -d /bot -s /sbin/nologin botuser

WORKDIR /bot
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=builder /install /usr/local
COPY . .
RUN chmod +x /bot/entrypoint.sh && chown -R botuser:botuser /bot
USER botuser
EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

ENTRYPOINT ["/bot/entrypoint.sh"]
CMD ["python", "-u", "run.py"]