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

### Windows + WSL Local Ollama

If Ollama runs on Windows and Docker runs from WSL or Docker Desktop, use the local compose file. This file does not start the air-gapped Ollama container; it points the backend to your Windows Ollama instance.

```bash
docker compose -f docker-compose.local.yml up -d --build
```

If `host.docker.internal` does not resolve inside WSL, find the Windows host IP:

```bash
awk '/nameserver/ {print $2; exit}' /etc/resolv.conf
```

Then pass it explicitly:

```bash
OLLAMA_URL=http://WINDOWS_HOST_IP:11434 \
docker compose -f docker-compose.local.yml up -d --build
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

The first required step on the air-gapped VM is installing Docker from the bundled RPMs. The archive must already contain all Docker Engine and Compose RPM dependencies under `deploy/offline-bundle/rpms`.

Manual Docker install command:

```bash
sudo dnf install -y deploy/offline-bundle/rpms/*.rpm
sudo systemctl enable --now docker
docker --version
docker compose version
```

The provided setup script performs this Docker installation automatically before loading images and starting the app:

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

## 4. Backend RAG Dependency Modes

The default backend image installs only lightweight Python dependencies. This makes local Windows/WSL testing reliable and avoids compiling NumPy inside a slim Python image.

Default local RAG mode:

- uses deterministic hashed embeddings
- performs local retrieval over uploaded files
- requires no FAISS, NumPy, Torch, or SentenceTransformers

Optional full RAG dependencies are listed in:

```text
backend/requirements-rag-full.txt
```

Use that file only on a connected staging machine where wheels are available or native builds are expected. The application code automatically uses FAISS and `all-MiniLM-L6-v2` when those packages and local model files are present; otherwise it falls back to the no-native local retriever.

The backend Dockerfile defaults to:

```text
python:3.12-slim-bookworm
```

This is intentional for local and air-gapped reliability. Python `3.14` can trigger native builds for packages such as `pydantic-core`, which then require Rust and a C linker in the image. To override the base image on a connected staging machine:

```bash
docker build --build-arg PYTHON_IMAGE=python:3.14.4-slim-bookworm -t loomin-docs-backend:py314 backend
```
