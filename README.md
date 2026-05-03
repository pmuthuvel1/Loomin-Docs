# Loomin Docs

Loomin Docs is an air-gapped collaborative text editor with a React/Next.js workspace, Python/FastAPI RAG engine, SQLite persistence, local file isolation, and Ollama-backed AI assistance.

Current version choices were checked on May 3, 2026: React `19.2`, Next.js `16.2.4`, and Python `3.14.4`. The backend Docker image defaults to Python `3.12-slim-bookworm` because the FastAPI/Pydantic ecosystem has reliable prebuilt wheels there; Python `3.14` can force native Rust/C builds in slim images.

## Repository

- `frontend/`: Next.js + React + TypeScript editor UI.
- `backend/`: FastAPI, SQLite, RAG, PII sanitization, Ollama integration.
- `deploy/`: Modelfiles, offline setup, bundle staging folders.
- `backend/tests/verify_faithfulness.py`: local RAG faithfulness smoke test.

## Air-Gapped Setup On RHEL 9

There are two build paths:

- Development build: use this when you have internet access and want to run locally.
- Air-gapped package build: use this to create the final archive for a clean RHEL 9 VM with no internet access.

### Development Build

From the repository root on a machine with Docker access:

```bash
docker compose build
docker compose up -d
```

Open the app:

```text
http://localhost:3000
```

Check the backend:

```text
http://localhost:8000/health
```

### Air-Gapped Package Build

Run these steps on an internet-connected Linux or RHEL-compatible staging machine. The air-gapped RHEL 9 VM must not build from source or pull anything from the network.

Prepare Ollama models:

```bash
ollama pull llama3
ollama pull mistral
ollama create loomin-llama3 -f deploy/Modelfile.llama3
ollama create loomin-mistral -f deploy/Modelfile.mistral
cp -a ~/.ollama/. deploy/offline-bundle/ollama-models/
```

Download Docker RPMs and dependencies:

```bash
dnf download --resolve --destdir deploy/offline-bundle/rpms \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Build and export Docker images:

```bash
chmod +x deploy/prepare_offline_bundle.sh
./deploy/prepare_offline_bundle.sh
```

Expected exported images:

```text
deploy/offline-bundle/images/loomin-docs-frontend.tar
deploy/offline-bundle/images/loomin-docs-backend.tar
deploy/offline-bundle/images/loomin-docs-ollama.tar
```

Create the final bootstrap archive:

```bash
tar -czf loomin-docs-bootstrap.tar.gz \
  deploy README.md DEPLOYMENT.md ARCHITECTURE.md backend/tests/verify_faithfulness.py
```

### Air-Gapped RHEL 9 Install

Copy `loomin-docs-bootstrap.tar.gz` to the clean RHEL 9 VM, then run:

```bash
tar -xzf loomin-docs-bootstrap.tar.gz
chmod +x deploy/setup.sh
./deploy/setup.sh
```

`deploy/setup.sh` uses `deploy/docker-compose.airgap.yml`, which references only preloaded images and does not require source build contexts.

Open:

```text
http://localhost:3000
```

## How Summarization Works

The editor sends selected text or a saved document to the FastAPI backend. The backend masks PII, retrieves relevant chunks from the user's private RAG folder, builds a grounded prompt, and calls the local Ollama API at `http://ollama:11434/api/generate`.

Main paths:

- Sidebar selection summary: `POST /users/{user}/assistant` with `action: "summarize"`.
- Saved document summary: `POST /users/{user}/documents/{doc_id}/summarize`.

The response includes the summary/edit text, clickable chunk citations, `request_id`, retrieval latency, generation latency, token speed, and context-window usage metadata.

## Model Weights

The VM has no internet access, so do not run `ollama pull` there. Prepare models on staging and bake them into the prebuilt Ollama image:

```bash
ollama pull llama3
ollama pull mistral
ollama create loomin-llama3 -f deploy/Modelfile.llama3
ollama create loomin-mistral -f deploy/Modelfile.mistral
cp -a ~/.ollama/. deploy/offline-bundle/ollama-models/
./deploy/prepare_offline_bundle.sh
```

The exported `deploy/offline-bundle/images/loomin-docs-ollama.tar` contains the Ollama runtime plus `/root/.ollama` model manifests and blobs. On the RHEL 9 VM, `deploy/setup.sh` only loads this image; it does not pull models or depend on a network.

## Security And Observability

The backend maps each user to `/mnt/uploads/users/{user}` and validates resolved paths before reads/writes. Uploads are limited to `.pdf`, `.md`, and `.txt`, file permissions are tightened, PII-like secrets are masked before LLM calls, and every document/file/assistant event is appended to `/mnt/uploads/audit.log`.

AI responses include `request_id`, retrieval latency, generation latency, estimated prompt tokens, context window, and token generation speed.

## Verification

Inside the backend image or a prepared Python environment:

```bash
python backend/tests/verify_faithfulness.py
```

The script verifies that retrieval is grounded in a local fixture and does not introduce unsupported claims.

## Note On Pyodide Constraints

The production backend is FastAPI in Docker. The RAG implementation also contains a no-install fallback path that avoids subprocess and package installation assumptions: if FAISS or SentenceTransformers are unavailable, it uses deterministic local hash embeddings and cosine ranking over files already present under `/mnt/uploads`.

For a strict browser-Pyodide evaluator, `backend/app/pyodide_engine.py` is pure standard library code. It uses `os.listdir('/mnt/uploads')`, reads only user-scoped `.md` and `.txt` files, and performs local hashed-vector retrieval without package installation.

## Backend Dependency Modes

`backend/requirements.txt` is the default local/runtime dependency set and intentionally avoids native ML packages. This prevents local Docker builds from compiling NumPy in slim Python images.

`backend/requirements-rag-full.txt` lists optional FAISS, NumPy, and SentenceTransformers dependencies for a connected staging build. When those packages and local model files are present, `backend/app/rag.py` uses them. Otherwise it falls back to deterministic local hash embeddings.

The backend Dockerfile accepts a Python image override:

```bash
docker build --build-arg PYTHON_IMAGE=python:3.14.4-slim-bookworm -t loomin-docs-backend:py314 backend
```

Use that only if you also provide the compiler/Rust toolchain or a fully prebuilt wheelhouse. For normal local and air-gapped runtime builds, keep the default Python `3.12` image.
