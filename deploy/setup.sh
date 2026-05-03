#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="${ROOT}/offline-bundle"
PROJECT_ROOT="$(cd "${ROOT}/.." && pwd)"

echo "[1/7] Installing Docker RPMs from ${BUNDLE}/rpms"
if ! command -v docker >/dev/null 2>&1; then
  sudo dnf install -y "${BUNDLE}"/rpms/*.rpm
fi

echo "[2/7] Enabling Docker"
sudo systemctl enable --now docker

echo "[3/7] Installing docker compose plugin if bundled"
if [ -f "${BUNDLE}/docker-compose" ]; then
  sudo install -m 0755 "${BUNDLE}/docker-compose" /usr/local/bin/docker-compose
fi

echo "[4/7] Loading sideloaded Docker images"
for image in "${BUNDLE}"/images/*.tar; do
  [ -e "${image}" ] || { echo "No image tar files found in ${BUNDLE}/images"; exit 1; }
  sudo docker load -i "${image}"
done

echo "[5/7] Restoring persistent upload seed"
sudo mkdir -p /mnt/uploads
sudo cp -a "${BUNDLE}/seed/." /mnt/uploads/
sudo chown -R 1000:1000 /mnt/uploads || true
sudo find /mnt/uploads/users -type d -exec chmod 700 {} \;
sudo find /mnt/uploads/users -type f -exec chmod 600 {} \;

echo "[6/7] Verifying prebuilt Ollama image contains model blobs"
sudo docker image inspect loomin-docs-ollama:offline >/dev/null

echo "[7/7] Starting Loomin Docs"
cd "${PROJECT_ROOT}"
if docker compose version >/dev/null 2>&1; then
  sudo docker compose -f "${ROOT}/docker-compose.airgap.yml" up -d
else
  sudo docker-compose -f "${ROOT}/docker-compose.airgap.yml" up -d
fi

echo "Loomin Docs is available at http://localhost:3000"
echo "Backend health: http://localhost:8000/health"
