"""
Pyodide-safe local RAG helper.

This module intentionally uses only the Python standard library. It does not
call pip, subprocess, micropycip, native extensions, or the network. It reads
files from /mnt/uploads, ranks chunks with deterministic hashed term vectors,
and returns citation-ready snippets.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from pathlib import Path

UPLOAD_ROOT = Path("/mnt/uploads")
ALLOWED = {".md", ".txt"}


def _safe_files(user: str) -> list[Path]:
    root = (UPLOAD_ROOT / "users" / user / "rag").resolve()
    base = UPLOAD_ROOT.resolve()
    if base not in root.parents:
        raise ValueError("Invalid upload root")
    if not root.exists():
        return []
    return [path for path in root.iterdir() if path.is_file() and path.suffix.lower() in ALLOWED]


def _embed(text: str, dims: int = 256) -> list[float]:
    vec = [0.0] * dims
    for token in re.findall(r"[A-Za-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        idx = int.from_bytes(digest[:4], "big") % dims
        vec[idx] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _chunks(path: Path, size: int = 900, overlap: int = 160) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    out = []
    start = 0
    while start < len(text):
        body = text[start : start + size].strip()
        if body:
            cid = hashlib.sha1(f"{path.name}:{start}:{body[:32]}".encode()).hexdigest()[:12]
            out.append({"file": path.name, "chunk_id": f"chunk-{cid}", "text": body})
        start += size - overlap
    return out


def retrieve(user: str, question: str, limit: int = 5) -> list[dict[str, object]]:
    """Return ranked local snippets for a user from /mnt/uploads/users/{user}/rag."""
    query = _embed(question)
    ranked = []
    for path in _safe_files(user):
        for chunk in _chunks(path):
            emb = _embed(str(chunk["text"]))
            score = sum(a * b for a, b in zip(query, emb))
            ranked.append({**chunk, "score": score})
    ranked.sort(key=lambda item: float(item["score"]), reverse=True)
    return ranked[:limit]


def list_uploads() -> list[str]:
    """Mirror the requested Pyodide discovery pattern."""
    if not UPLOAD_ROOT.exists():
        return []
    return os.listdir(str(UPLOAD_ROOT))
