"""Index the multi-target therapeutic strategy chunks into ChromaDB.

This script is the bridge between the data-preparation notebooks and the
retrieval/RAG layer. It reads the chunk JSONL created by notebook 16 and builds
a local ChromaDB collection for semantic search.

Input:
- data/processed/multi_target_therapy_knowledge_base_chunks.jsonl

Output:
- chroma_db/ local ChromaDB index
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"

DEFAULT_CHUNKS_FILE = PROCESSED_DIR / "multi_target_therapy_knowledge_base_chunks.jsonl"
DEFAULT_COLLECTION_NAME = "multi_target_therapeutic_strategy"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL rows from disk."""
    if not path.exists():
        raise FileNotFoundError(f"Missing required chunks file: {path}")

    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} in {path}") from exc
    return rows


def normalize_metadata_value(value: Any) -> str | int | float | bool:
    """Convert metadata values to Chroma-compatible scalar types."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def normalize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    return {key: normalize_metadata_value(value) for key, value in metadata.items()}


def validate_chunks(chunks: list[dict[str, Any]]) -> None:
    if not chunks:
        raise ValueError("No chunks found. Run notebook 16 before indexing.")

    required_fields = {"id", "text", "metadata"}
    missing_rows = [index for index, chunk in enumerate(chunks, start=1) if not required_fields.issubset(chunk)]
    if missing_rows:
        raise ValueError(f"Chunks missing required fields at rows: {missing_rows[:10]}")


def make_unique_ids(chunks: list[dict[str, Any]]) -> list[str]:
    """Return Chroma-safe unique IDs while preserving the original chunk ID."""
    seen: dict[str, int] = {}
    ids: list[str] = []

    for chunk in chunks:
        original_id = str(chunk["id"])
        seen[original_id] = seen.get(original_id, 0) + 1
        if seen[original_id] == 1:
            ids.append(original_id)
        else:
            ids.append(f"{original_id}::dup{seen[original_id]}")
    return ids


def get_chroma_collection(collection_name: str, reset: bool = False):
    """Create or load the ChromaDB collection."""
    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError as exc:
        raise RuntimeError("ChromaDB is required. Run `uv sync` first.") from exc

    if reset and CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embedding_function = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_function,
        metadata={"description": "Multi-target therapeutic strategy evidence chunks"},
    )


def index_chunks(
    chunks_file: Path = DEFAULT_CHUNKS_FILE,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    reset: bool = True,
):
    """Load chunk JSONL and index it into ChromaDB."""
    chunks = load_jsonl(chunks_file)
    validate_chunks(chunks)

    collection = get_chroma_collection(collection_name=collection_name, reset=reset)

    ids = make_unique_ids(chunks)
    documents = [str(chunk["text"]) for chunk in chunks]
    metadatas = []
    for chunk in chunks:
        metadata = normalize_metadata(chunk.get("metadata", {}))
        metadata["original_chunk_id"] = str(chunk["id"])
        metadatas.append(metadata)

    # Chroma can insert all 207 chunks in one call, keeping this simple and readable.
    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return collection, chunks


def query_collection(
    question: str,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    top_k: int = 5,
    target_symbol: str | None = None,
) -> dict[str, Any]:
    """Query an already-built ChromaDB collection."""
    collection = get_chroma_collection(collection_name=collection_name, reset=False)
    where = {"target_symbol": target_symbol} if target_symbol else None
    return collection.query(query_texts=[question], n_results=top_k, where=where)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index multi-target therapy chunks into ChromaDB.")
    parser.add_argument("--chunks-file", type=Path, default=DEFAULT_CHUNKS_FILE)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--no-reset", action="store_true", help="Append to existing collection instead of rebuilding chroma_db/.")
    parser.add_argument("--smoke-query", default="Which approved therapies target EGFR?")
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    collection, chunks = index_chunks(
        chunks_file=args.chunks_file,
        collection_name=args.collection_name,
        reset=not args.no_reset,
    )

    targets = sorted({chunk.get("metadata", {}).get("target_symbol", "") for chunk in chunks})
    targets = [target for target in targets if target]

    print("Multi-target ChromaDB index built")
    print("=" * 70)
    print("Chunks indexed:", len(chunks))
    print("Collection:", args.collection_name)
    print("Chroma path:", CHROMA_DIR)
    print("Targets:", ", ".join(targets))

    response = collection.query(query_texts=[args.smoke_query], n_results=args.top_k)
    print()
    print("Smoke query:", args.smoke_query)
    for rank, metadata in enumerate(response["metadatas"][0], start=1):
        print(
            f"{rank}. {metadata.get('target_symbol', '')} | "
            f"{metadata.get('drug_name', '')} | "
            f"score={metadata.get('evidence_score', '')} | "
            f"strength={metadata.get('evidence_strength', '')}"
        )


if __name__ == "__main__":
    main()
