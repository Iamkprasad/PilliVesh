#!/usr/bin/env bash
PATTERN="runtime.server.app"
if pkill -f "$PATTERN" 2>/dev/null; then
  echo "Dashboard server stopped."
else
  echo "No dashboard server running (pattern: $PATTERN)."
  echo "If started manually, stop it with Ctrl+C."
fi
