#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${ROOT}/.." && pwd)"
BUNDLE="${ROOT}/offline-bundle"

mkdir -p "${BUNDLE}/images" "${BUNDLE}/rpms" "${BUNDLE}/ollama-models"

echo "Build images on an internet-connected staging RHEL-compatible machine first."
cd "${PROJECT_ROOT}"
docker pull ollama/ollama:latest
docker tag ollama/ollama:latest ollama/ollama:offline-base

if [ ! -d "${BUNDLE}/ollama-models/models" ]; then
  cat >&2 <<'MSG'
Missing deploy/offline-bundle/ollama-models/models.
Prepare the Ollama model store first:
  ollama pull llama3
  ollama pull mistral
  ollama create loomin-llama3 -f deploy/Modelfile.llama3
  ollama create loomin-mistral -f deploy/Modelfile.mistral
  cp -a ~/.ollama/. deploy/offline-bundle/ollama-models/
MSG
  exit 1
fi

docker build -f deploy/ollama/Dockerfile -t loomin-docs-ollama:offline deploy
docker compose build

docker save loomin-docs-frontend:offline -o "${BUNDLE}/images/loomin-docs-frontend.tar"
docker save loomin-docs-backend:offline -o "${BUNDLE}/images/loomin-docs-backend.tar"
docker save loomin-docs-ollama:offline -o "${BUNDLE}/images/loomin-docs-ollama.tar"

cat <<'MSG'
Next manual staging steps:
1. Place RHEL 9 Docker Engine and compose RPM dependencies in deploy/offline-bundle/rpms.
2. Pull/create Ollama models on staging before running this script:
   ollama pull llama3
   ollama pull mistral
   ollama create loomin-llama3 -f deploy/Modelfile.llama3
   ollama create loomin-mistral -f deploy/Modelfile.mistral
3. Copy ~/.ollama contents into deploy/offline-bundle/ollama-models.
4. Create the archive:
   tar -czf loomin-docs-bootstrap.tar.gz deploy README.md DEPLOYMENT.md ARCHITECTURE.md backend/tests/verify_faithfulness.py
MSG
