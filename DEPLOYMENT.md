# Deployment Steps

## 1. Development Build

Use this on a connected development machine:

```bash
docker compose build
docker compose up -d
```

Open:

```text
http://localhost:3000
```

Backend health:

```text
http://localhost:8000/health
```

## 2. Prepare Air-Gapped Bundle

Run these steps on an internet-connected Linux or RHEL-compatible staging machine.

Prepare Ollama models:

```bash
ollama pull llama3
ollama pull mistral
ollama create loomin-llama3 -f deploy/Modelfile.llama3
ollama create loomin-mistral -f deploy/Modelfile.mistral
cp -a ~/.ollama/. deploy/offline-bundle/ollama-models/
```

Download Docker RPMs:

```bash
dnf download --resolve --destdir deploy/offline-bundle/rpms \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Build and export images:

```bash
chmod +x deploy/prepare_offline_bundle.sh
./deploy/prepare_offline_bundle.sh
```

Expected files:

```text
deploy/offline-bundle/images/loomin-docs-frontend.tar
deploy/offline-bundle/images/loomin-docs-backend.tar
deploy/offline-bundle/images/loomin-docs-ollama.tar
```

Create the final archive:

```bash
tar -czf loomin-docs-bootstrap.tar.gz \
  deploy README.md DEPLOYMENT.md ARCHITECTURE.md backend/tests/verify_faithfulness.py
```

## 3. Install On Air-Gapped RHEL 9

Copy `loomin-docs-bootstrap.tar.gz` to the VM.

```bash
tar -xzf loomin-docs-bootstrap.tar.gz
chmod +x deploy/setup.sh
./deploy/setup.sh
```

The setup script installs Docker from bundled RPMs, loads prebuilt image tar files, seeds `/mnt/uploads`, verifies the prebuilt Ollama image, and starts the services with `deploy/docker-compose.airgap.yml`.

Open:

```text
http://localhost:3000
```
