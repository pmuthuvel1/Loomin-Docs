from pathlib import Path
import os

UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", "/mnt/uploads"))
DB_PATH = Path(os.getenv("DB_PATH", "/mnt/uploads/loomin.sqlite3"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
AUDIT_LOG = Path(os.getenv("AUDIT_LOG", "/mnt/uploads/audit.log"))
DEFAULT_CONTEXT_WINDOW = int(os.getenv("CONTEXT_WINDOW", "8192"))
ALLOWED_EXTENSIONS = {".md", ".txt", ".pdf"}
MODEL_MAP = {
    "llama3-local": os.getenv("LLAMA_MODEL", "loomin-llama3"),
    "mistral-local": os.getenv("MISTRAL_MODEL", "loomin-mistral")
}
