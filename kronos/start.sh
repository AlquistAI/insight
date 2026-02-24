#!/usr/bin/env bash
set -o errexit

# Run the prestart.py script
echo "Running the prestart.py script"
python3 /home/app/kronos/prestart.py

# Start Uvicorn
exec /usr/local/bin/uvicorn \
  --host "0.0.0.0" \
  --port "${KRONOS_CONTAINER_PORT:-9625}" \
  --log-level "${KRONOS_LOG_LEVEL:-debug}" \
  run:fast_app
