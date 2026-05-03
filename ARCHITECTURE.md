# Architecture

```mermaid
flowchart LR
  U[Browser User] --> FE[Next.js React Editor]
  FE -->|Documents, uploads, assistant requests| BE[FastAPI Air-Gapped Engine]
  BE --> DB[(SQLite: users, docs, versions, chat)]
  BE --> FS[/mnt/uploads/users/{user}/]
  BE --> RAG[FAISS or Hash Vector RAG]
  RAG --> FS
  BE -->|sanitized prompt + retrieved snippets| OL[Ollama Local LLM]
  OL -->|answer, edit, timing| BE
  BE -->|citations + metadata| FE
  BE --> LOG[(audit.log)]
```

The frontend never calls Ollama directly. All prompts pass through the backend PII sanitizer, user-folder resolver, retrieval layer, and audit logger.
