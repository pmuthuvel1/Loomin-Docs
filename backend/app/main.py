from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import ALLOWED_EXTENSIONS, DEFAULT_CONTEXT_WINDOW, MODEL_MAP
from .db import connect, ensure_user, init_db
from .ollama import generate
from .rag import RagIndex, file_record
from .security import audit, ensure_inside, sanitize_for_llm, user_root, utcnow

app = FastAPI(title="Loomin Docs Air-Gapped Engine", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DocumentIn(BaseModel):
    title: str
    content: str


class AssistantIn(BaseModel):
    action: str
    model: str
    question: str
    document: str
    selection: str = ""


class SummarizeDocumentIn(BaseModel):
    model: str = "llama3-local"


@app.on_event("startup")
def startup() -> None:
    init_db()
    for user in ("alice", "bob"):
        root = user_root(user)
        ensure_user(user, root)
        seed = root / "documents" / "welcome.md"
        if seed.exists():
            with connect() as db:
                existing = db.execute("SELECT id FROM documents WHERE user_id=? LIMIT 1", (user,)).fetchone()
                if not existing:
                    now = utcnow()
                    content = seed.read_text(encoding="utf-8", errors="ignore")
                    db.execute(
                        "INSERT INTO documents(user_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (user, seed.stem.replace("-", " ").title(), content, now, now),
                    )


def get_user(user: str) -> Path:
    try:
        root = user_root(user)
        ensure_user(user, root)
        return root
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/users/{user}/documents")
def list_documents(user: str) -> list[dict[str, object]]:
    get_user(user)
    audit("documents.list", user)
    with connect() as db:
        rows = db.execute(
            "SELECT id, title, updated_at, length(content) AS bytes FROM documents WHERE user_id=? ORDER BY updated_at DESC",
            (user,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/users/{user}/documents")
def create_document(user: str, payload: DocumentIn) -> dict[str, int]:
    get_user(user)
    now = utcnow()
    with connect() as db:
        cur = db.execute(
            "INSERT INTO documents(user_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (user, payload.title, payload.content, now, now),
        )
        doc_id = int(cur.lastrowid)
        db.execute("INSERT INTO document_versions(document_id, content, created_at) VALUES (?, ?, ?)", (doc_id, payload.content, now))
    audit("document.create", user, document_id=doc_id)
    return {"id": doc_id}


@app.get("/users/{user}/documents/{doc_id}")
def get_document(user: str, doc_id: int) -> dict[str, object]:
    get_user(user)
    with connect() as db:
        row = db.execute("SELECT id, title, content FROM documents WHERE id=? AND user_id=?", (doc_id, user)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    audit("document.read", user, document_id=doc_id)
    return dict(row)


@app.put("/users/{user}/documents/{doc_id}")
def update_document(user: str, doc_id: int, payload: DocumentIn) -> dict[str, int]:
    get_user(user)
    now = utcnow()
    with connect() as db:
        existing = db.execute("SELECT id FROM documents WHERE id=? AND user_id=?", (doc_id, user)).fetchone()
        if not existing:
            raise HTTPException(404, "Document not found")
        db.execute(
            "UPDATE documents SET title=?, content=?, updated_at=? WHERE id=? AND user_id=?",
            (payload.title, payload.content, now, doc_id, user),
        )
        db.execute("INSERT INTO document_versions(document_id, content, created_at) VALUES (?, ?, ?)", (doc_id, payload.content, now))
    audit("document.update", user, document_id=doc_id)
    return {"id": doc_id}


@app.get("/users/{user}/files")
def list_files(user: str) -> list[dict[str, object]]:
    root = get_user(user) / "rag"
    audit("files.list", user)
    return [file_record(path) for path in sorted(root.glob("*")) if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS]


@app.post("/users/{user}/files")
async def upload_file(user: str, file: UploadFile = File(...)) -> dict[str, object]:
    root = get_user(user) / "rag"
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only .pdf, .md, and .txt files are supported")
    target = ensure_inside(root / Path(file.filename or "upload").name, root)
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    try:
        target.chmod(0o600)
    except PermissionError:
        pass
    audit("file.upload", user, file=target.name, sha256=file_record(target)["sha256"])
    return file_record(target)


def build_prompt(payload: AssistantIn, citations: list[dict[str, object]]) -> str:
    context = "\n\n".join(f"[{c['chunk_id']}] {c['file']}\n{c['quote']}" for c in citations)
    instruction = {
        "chat": "Answer the user's question using only the retrieved local context. Cite chunk ids inline.",
        "summarize": "Summarize the selected text concisely and return a replacement suitable for the document.",
        "improve": "Improve clarity, grammar, and structure of the selected text. Preserve meaning and return replacement text.",
    }.get(payload.action, "Answer using only the retrieved local context.")
    return f"""You are Loomin, an offline document assistant.
Rules:
- Use only the document and retrieved context below.
- If the answer is not grounded in context, say what is missing.
- Masked PII must remain masked.
- For edit actions, start with REPLACEMENT: on its own line followed by the document-ready text.

Instruction: {instruction}

Active document:
{sanitize_for_llm(payload.document)[:12000]}

Selected text:
{sanitize_for_llm(payload.selection)}

Retrieved context:
{context}

User request:
{sanitize_for_llm(payload.question)}
"""


@app.post("/users/{user}/assistant")
async def assistant(user: str, payload: AssistantIn) -> dict[str, object]:
    request_id = str(uuid.uuid4())
    root = get_user(user)
    model = MODEL_MAP.get(payload.model, MODEL_MAP["llama3-local"])
    retrieval_started = time.perf_counter()
    chunks = RagIndex(root / "rag").search(payload.question or payload.selection or payload.document, limit=5)
    retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000)
    citations = [
        {"file": c.file, "chunk_id": c.chunk_id, "score": c.score, "quote": c.text[:360]}
        for c in chunks
    ]
    prompt = build_prompt(payload, citations)
    try:
        answer, gen_meta = await generate(model, prompt)
    except Exception as exc:
        answer = f"Local Ollama request failed: {exc}"
        gen_meta = {"generation_ms": 0, "tokens_per_second": 0.0}
    replacement = None
    if "REPLACEMENT:" in answer:
        replacement = answer.split("REPLACEMENT:", 1)[1].strip()
    elif payload.action in {"summarize", "improve"}:
        replacement = answer.strip()
    metadata = {
        "retrieval_ms": retrieval_ms,
        "generation_ms": gen_meta["generation_ms"],
        "tokens_per_second": float(gen_meta["tokens_per_second"]),
        "prompt_tokens_estimate": max(1, len(prompt) // 4),
        "context_window": DEFAULT_CONTEXT_WINDOW,
    }
    with connect() as db:
        db.execute(
            "INSERT INTO chat_history(user_id, request_id, model, question, answer, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user, request_id, model, payload.question, answer, json.dumps(metadata), utcnow()),
        )
    audit("assistant.request", user, request_id=request_id, model=model, action=payload.action, citations=len(citations))
    return {
        "request_id": request_id,
        "answer": answer,
        "replacement": replacement,
        "citations": citations,
        "metadata": metadata,
    }


@app.post("/users/{user}/documents/{doc_id}/summarize")
async def summarize_document(user: str, doc_id: int, payload: SummarizeDocumentIn) -> dict[str, object]:
    with connect() as db:
        row = db.execute("SELECT title, content FROM documents WHERE id=? AND user_id=?", (doc_id, user)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    audit("document.summarize", user, document_id=doc_id)
    return await assistant(
        user,
        AssistantIn(
            action="summarize",
            model=payload.model,
            question=f"Summarize the document titled {row['title']}",
            document=row["content"],
            selection=row["content"],
        ),
    )
