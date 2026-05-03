from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import AUDIT_LOG, UPLOAD_ROOT

SAFE_USER = re.compile(r"^[a-zA-Z0-9_-]{1,48}$")
PII_PATTERNS = [
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL]"),
    (re.compile(r"\b(?:\+?\d[\d -]{8,}\d)\b"), "[PHONE]"),
    (re.compile(r"\b(?:sk|pk|api|key|token|secret)_[A-Za-z0-9_\-]{12,}\b", re.I), "[SECRET]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[CARD]"),
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def user_root(user: str) -> Path:
    if not SAFE_USER.match(user):
        raise ValueError("Invalid user id")
    root = (UPLOAD_ROOT / "users" / user).resolve()
    base = UPLOAD_ROOT.resolve()
    if base not in root.parents and root != base:
        raise ValueError("Invalid user path")
    for child in ("documents", "rag"):
        path = root / child
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except PermissionError:
            pass
    return root


def ensure_inside(path: Path, parent: Path) -> Path:
    resolved = path.resolve()
    allowed = parent.resolve()
    if allowed not in resolved.parents and resolved != allowed:
        raise ValueError("Path escapes user folder")
    return resolved


def sanitize_for_llm(text: str) -> str:
    redacted = text
    for pattern, replacement in PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(event: str, user: str, **fields: Any) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": utcnow(), "event": event, "user": user, **fields}
    with AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
