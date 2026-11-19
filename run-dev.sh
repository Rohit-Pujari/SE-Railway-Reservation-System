#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

cd "$ROOT_DIR"

for command_name in uv npm; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$command_name" >&2
    exit 1
  fi
done

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  printf 'Missing .env. Copy .env.example to .env and set your MySQL credentials first.\n' >&2
  exit 1
fi

if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  uv venv "$ROOT_DIR/.venv"
fi

if ! "$ROOT_DIR/.venv/bin/python" -c 'import django, rest_framework, mysql.connector' >/dev/null 2>&1; then
  printf 'Installing Python requirements into the project .venv...\n'
  uv pip install --python "$ROOT_DIR/.venv/bin/python" -r "$ROOT_DIR/requirements.txt"
fi

if [[ ! -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ]]; then
  printf 'Installing React frontend requirements...\n'
  npm ci --prefix "$ROOT_DIR/frontend"
fi

export DJANGO_HOST="$BACKEND_HOST"
export DJANGO_PORT="$BACKEND_PORT"
export DJANGO_API_TARGET="http://${BACKEND_HOST}:${BACKEND_PORT}"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]]; then
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]]; then
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
  exit "$exit_code"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf 'Django API: http://%s:%s\n' "$BACKEND_HOST" "$BACKEND_PORT"
printf 'React app:  http://%s:%s\n' "$FRONTEND_HOST" "$FRONTEND_PORT"
printf 'MySQL must be running with the existing railway_reservation schema. Press Ctrl+C to stop both servers.\n'

"$ROOT_DIR/.venv/bin/python" -m backend.manage runserver "${BACKEND_HOST}:${BACKEND_PORT}" --noreload &
BACKEND_PID=$!

(cd "$ROOT_DIR/frontend" && "$ROOT_DIR/frontend/node_modules/.bin/vite" --host "$FRONTEND_HOST" --port "$FRONTEND_PORT") &
FRONTEND_PID=$!

if wait -n "$BACKEND_PID" "$FRONTEND_PID"; then
  exit_code=0
else
  exit_code=$?
fi
exit "$exit_code"
