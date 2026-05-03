#!/usr/bin/env bash
set -euo pipefail

if [ ! -d /root/.ollama/models ] || [ -z "$(find /root/.ollama/models -type f 2>/dev/null | head -n 1)" ]; then
  echo "ERROR: /root/.ollama/models is empty. Build the offline image after copying model blobs into deploy/offline-bundle/ollama-models." >&2
  exit 64
fi

exec /bin/ollama serve
