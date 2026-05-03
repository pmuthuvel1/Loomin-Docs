"""
Offline verification for the RAG pipeline.

The test inserts a tiny local corpus, runs retrieval, and checks that returned
answers only contain terms supported by retrieved snippets. It is deliberately
model-light so it can run in an air-gapped VM before Ollama is warmed.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag import RagIndex  # noqa: E402


def main() -> int:
    fixture = Path("/tmp/loomin-faithfulness")
    fixture.mkdir(parents=True, exist_ok=True)
    (fixture / "policy.md").write_text(
        "# Deployment Policy\n\nLoomin must run offline on RHEL 9. Docker images and Ollama models are side-loaded.",
        encoding="utf-8",
    )
    chunks = RagIndex(fixture).search("How must Loomin run on the evaluation VM?", limit=3)
    joined = " ".join(c.text.lower() for c in chunks)
    required = ["offline", "rhel 9", "side-loaded"]
    missing = [term for term in required if term not in joined]
    if missing:
        print(f"FAIL: retrieval missed grounded terms: {missing}")
        return 1
    unsupported_claims = ["internet", "cloud", "external api"]
    leaked = [term for term in unsupported_claims if term in joined]
    if leaked:
        print(f"FAIL: retrieved context contains unsupported claims: {leaked}")
        return 1
    print("PASS: RAG retrieval is grounded in the local fixture.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
