# BIT Agents API — Render / container image
FROM python:3.11-slim-bookworm

WORKDIR /app

# Node is required for Meteora pool-creation scripts under scripts/
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/package.json scripts/package-lock.json* ./scripts/
RUN cd scripts && npm install --omit=dev

COPY . .

ENV PYTHONUNBUFFERED=1
ENV AGENTS_API_HOST=0.0.0.0

# Render injects PORT; default for local docker runs
EXPOSE 8765

CMD ["sh", "-c", "uvicorn agents_api:app --host 0.0.0.0 --port ${PORT:-8765}"]
