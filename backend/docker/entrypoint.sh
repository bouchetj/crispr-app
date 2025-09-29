#!/usr/bin/env bash
set -euo pipefail

APP_ENV=${APP_ENV:-prod}
APP_MODULE=${APP_MODULE:-main:app}
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

if [[ "${APP_ENV}" == "dev" ]]; then
  exec uvicorn "${APP_MODULE}" --host "${HOST}" --port "${PORT}" --reload
fi

WORKERS=${UVICORN_WORKERS:-4}
exec uvicorn "${APP_MODULE}" --host "${HOST}" --port "${PORT}" --workers "${WORKERS}"
