#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_ACTIVATE="${ROOT_DIR}/.venv/bin/activate"

if [[ -f "${VENV_ACTIVATE}" ]]; then
  # shellcheck disable=SC1091
  source "${VENV_ACTIVATE}"
else
  echo "Virtual environment not found at ${VENV_ACTIVATE}." >&2
  echo "Create it with 'python3 -m venv .venv' and install dependencies before running this script." >&2
  exit 1
fi

cd "${ROOT_DIR}/src/backend"

declare -a CHILD_PIDS=()
declare -a CHILD_LABELS=()

start_process() {
  local label=$1
  shift
  echo "▶ Starting ${label}: $*"
  "$@" &
  local pid=$!
  CHILD_PIDS+=("${pid}")
  CHILD_LABELS+=("${label}")
}

stop_children() {
  for pid in "${CHILD_PIDS[@]:-}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
}

cleanup() {
  local exit_code=$1
  trap - EXIT
  stop_children
  wait 2>/dev/null || true
  exit "${exit_code}"
}

trap 'cleanup $?' EXIT

on_interrupt() {
  echo
  echo "Interrupt received. Shutting down..."
  exit 130
}

on_terminate() {
  echo
  echo "Terminate signal received. Shutting down..."
  exit 143
}

trap on_interrupt INT
trap on_terminate TERM

start_process "api" uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
start_process "celery-default" celery -A app.celery_app.celery_app worker -n default@%h
start_process "celery-ml" celery -A app.celery_app.celery_app worker -Q ml -n ml@%h

echo "All services are running. Press Ctrl+C to stop."

while true; do
  for idx in "${!CHILD_PIDS[@]}"; do
    pid=${CHILD_PIDS[$idx]}
    label=${CHILD_LABELS[$idx]}
    if ! kill -0 "${pid}" 2>/dev/null; then
      wait "${pid}" || true
      echo
      echo "Process '${label}' (pid ${pid}) exited. Stopping remaining services."
      exit 1
    fi
  done
  sleep 2
done
