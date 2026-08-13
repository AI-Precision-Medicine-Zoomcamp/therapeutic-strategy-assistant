"""Load final knowledge-base chunks with dlt into DuckDB."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.index_to_vectordb import DEFAULT_CHUNKS_FILE, load_jsonl  # noqa: E402


def chunk_rows(chunks_file: Path = DEFAULT_CHUNKS_FILE) -> Iterator[dict[str, Any]]:
    for row in load_jsonl(chunks_file):
        metadata = row.get("metadata", {})
        source = metadata.get("source") or metadata.get("source_table") or ""
        section = metadata.get("section") or metadata.get("source_table") or ""
        yield {
            "chunk_id": row.get("id"),
            "text": row.get("text"),
            "target_symbol": metadata.get("target_symbol"),
            "drug_name": metadata.get("drug_name"),
            "source": source,
            "evidence_strength": metadata.get("evidence_strength"),
            "evidence_score": metadata.get("evidence_score"),
            "section": section,
        }


def run_pipeline(chunks_file: Path = DEFAULT_CHUNKS_FILE):
    try:
        import dlt
    except ImportError as exc:
        raise RuntimeError("Install dlt first with `uv sync`, then run this script again.") from exc

    @dlt.resource(name="therapy_chunks", write_disposition="replace")
    def therapy_chunks():
        yield from chunk_rows(chunks_file)

    pipeline = dlt.pipeline(
        pipeline_name="therapeutic_strategy_ingestion",
        destination="duckdb",
        dataset_name="therapeutic_strategy",
    )
    return pipeline.run(therapy_chunks())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the dlt ingestion pipeline.")
    parser.add_argument("--chunks-file", type=Path, default=DEFAULT_CHUNKS_FILE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_info = run_pipeline(chunks_file=args.chunks_file)
    print(load_info)


if __name__ == "__main__":
    main()
