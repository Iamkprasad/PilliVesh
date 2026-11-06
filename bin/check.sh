#!/usr/bin/env bash
# One-screen PilliVesh health: RAM, llama, models, ports.
python3 -m runtime.model.runtime_config 2>/dev/null | grep -E "ram_available|llama_version"
python3 - <<'PY'
import socket
for p in (8080, 8081):
    try:
        s = socket.create_connection(('127.0.0.1', p), timeout=2)
        print(f"port {p}: open"); s.close()
    except OSError:
        print(f"port {p}: closed")
PY
