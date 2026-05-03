from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import ALLOWED_EXTENSIONS
from .security import ensure_inside, sanitize_for_llm, sha256_file

try:
    import faiss  # type: ignore
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover - intentionally supports Pyodide-like fallbacks
    faiss = None
    SentenceTransformer = None


@dataclass
class Chunk:
    chunk_id: str
    file: str
    text: str
    score: float = 0.0


class Embedder:
    def __init__(self) -> None:
        self.model = None
        if SentenceTransformer:
            try:
                self.model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
            except Exception:
                self.model = None

    def encode(self, texts: list[str]) -> np.ndarray:
        if self.model:
            vectors = self.model.encode(texts, normalize_embeddings=True)
            return np.asarray(vectors, dtype="float32")
        return np.asarray([hash_embedding(text) for text in texts], dtype="float32")


def hash_embedding(text: str, dims: int = 384) -> list[float]:
    vector = [0.0] * dims
    for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[idx] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type")
    if suffix == ".pdf":
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(file_name: str, text: str, size: int = 900, overlap: int = 160) -> list[Chunk]:
    clean = sanitize_for_llm(text)
    chunks: list[Chunk] = []
    start = 0
    while start < len(clean):
        piece = clean[start : start + size].strip()
        if piece:
            chunk_hash = hashlib.sha1(f"{file_name}:{start}:{piece[:64]}".encode()).hexdigest()[:12]
            chunks.append(Chunk(chunk_id=f"chunk-{chunk_hash}", file=file_name, text=piece))
        start += size - overlap
    return chunks


class RagIndex:
    def __init__(self, user_rag_dir: Path) -> None:
        self.user_rag_dir = user_rag_dir
        self.embedder = Embedder()
        self.chunks: list[Chunk] = []
        self.matrix: np.ndarray | None = None
        self.index = None

    def build(self) -> None:
        chunks: list[Chunk] = []
        for path in sorted(self.user_rag_dir.glob("*")):
            ensure_inside(path, self.user_rag_dir)
            if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS:
                chunks.extend(chunk_text(path.name, read_text(path)))
        self.chunks = chunks
        if not chunks:
            self.matrix = None
            self.index = None
            return
        self.matrix = self.embedder.encode([c.text for c in chunks])
        if faiss:
            self.index = faiss.IndexFlatIP(self.matrix.shape[1])
            self.index.add(self.matrix)

    def search(self, question: str, limit: int = 5) -> list[Chunk]:
        if not self.chunks:
            self.build()
        if not self.chunks or self.matrix is None:
            return []
        query = self.embedder.encode([sanitize_for_llm(question)])
        if self.index:
            scores, ids = self.index.search(query, min(limit, len(self.chunks)))
            return [Chunk(**{**self.chunks[int(i)].__dict__, "score": float(scores[0][pos])}) for pos, i in enumerate(ids[0]) if i >= 0]
        scores = self.matrix @ query[0]
        ranked = np.argsort(scores)[::-1][:limit]
        return [Chunk(**{**self.chunks[int(i)].__dict__, "score": float(scores[int(i)])}) for i in ranked]


def file_record(path: Path) -> dict[str, object]:
    return {
        "name": path.name,
        "size": path.stat().st_size,
        "modified_at": path.stat().st_mtime,
        "sha256": sha256_file(path),
    }
