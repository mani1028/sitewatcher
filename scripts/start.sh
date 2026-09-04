#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
fi

# Prefer Docker when available
if docker info >/dev/null 2>&1; then
  echo "Starting SiteWatch with Docker Compose…"
  docker compose up --build
  exit 0
fi

echo "Docker is not running."
echo "Start Docker Desktop, then run: docker compose up --build"
echo
echo "Or for local API-only development (requires Postgres + Redis):"
echo "  source .venv/bin/activate"
echo "  export DATABASE_URL=postgresql+asyncpg://sitewatch:sitewatch@localhost:5432/sitewatch"
echo "  uvicorn app.main:app --reload --app-dir backend --port 8000"
exit 1
