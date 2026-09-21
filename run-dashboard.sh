#!/usr/bin/env bash
set -e
LAB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${AI_LAB_HOST:-127.0.0.1}"
PORT="${AI_LAB_PORT:-8080}"
echo "LOCAL AI CONTROL CENTER"
echo "Lab: $LAB"
command -v python3 >/dev/null || { echo "python3 not found"; exit 1; }
for f in results/telemetry_latest.json results/benchmark_latest.json logs/runtime.jsonl; do
  [ -e "$LAB/$f" ] && echo "ok: $f" || echo "missing (will show Unavailable): $f"
done
# Refresh snapshot best-effort (never fails the launch).
python3 -m runtime.monitor.telemetry >/dev/null 2>&1 || true
echo "Server running."
echo "Open: http://$HOST:$PORT"
AI_LAB_HOST="$HOST" AI_LAB_PORT="$PORT" python3 -m runtime.server.app
