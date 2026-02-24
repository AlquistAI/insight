#!/usr/bin/env bash
set -o errexit

# Here you can run any operations needed before server start (e.g. migrations)
# ...

# Start Uvicorn
exec /usr/local/bin/uvicorn \
  --host "0.0.0.0" \
  --port "${RAGNAROK_CONTAINER_PORT:-9696}" \
  --log-level "${RAGNAROK_LOG_LEVEL:-debug}" \
  run:fast_app
