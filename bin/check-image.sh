#!/usr/bin/env bash
# One-screen health check for the PilliVesh image engine.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE="${AI_LAB_IMAGE_ENGINE:-$ROOT/bin/sd-server}"

echo "== PilliVesh image check =="
if [ -x "$ENGINE" ]; then
  echo "engine: OK ($ENGINE)"
else
  echo "engine: MISSING (run bin/install-image-engine.sh)"
fi
echo "models:"
python3 -m runtime.model.image_catalog 2>/dev/null || echo "  catalog unavailable"
echo "router:"
python3 -m runtime.model.image_router status 2>/dev/null || echo "  status unavailable"
echo "webapp: $ROOT/image_web/index.html"
