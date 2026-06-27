"""Week 3 retrieval prototype for the EGFR therapeutic strategy KB.

This intentionally stays simple:
- read retrieval-ready chunks from data/processed
- index them in a local ChromaDB collection
- run the Week 3 evaluation questions
- report whether retrieved chunks contain the expected source/category signal

No FastAPI, Streamlit, agent, or LLM summary is used here.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "egfr_therapy_knowledge_base_chunks.jsonl"
QUESTIONS_FILE = PROJECT_ROOT / "evaluation" / "retrieval_questions.jsonl"
RESULTS_FILE = PROJECT_ROOT / "evaluation" / "retrieval_results.json"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "egfr_therapeutic_strategy"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    rows: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def expected_terms(expected_source: str, category: str) -> list[str]:
    terms = []
    for part in expected_source.replace(";", "|").split("|"):
        part = part.strip().lower()
        if part:
            terms.append(part)
    category_lower = category.lower()
    if "approval" in category_lower:
        terms.extend(["approved", "max_phase"])
    if "clinical" in category_lower:
        terms.extend(["clinicaltrials.gov", "trial"])
    if "mechanism" in category_lower:
        terms.append("mechanism")
    if "ranking" in category_lower:
        terms.extend(["final evidence score", "score"])
    if "gap" in category_lower:
        terms.extend(["final evidence score", "score", "source references", "0.0"])
    if "target metadata" in category_lower:
        terms.extend(["uniprot", "protein"])
    return list(dict.fromkeys(terms))


def hit_for_question(documents: list[str], question: dict) -> bool:
    combined = "\n".join(documents).lower()
    terms = expected_terms(question["expected_source"], question["category"])
    return any(term in combined for term in terms)


def build_collection():
    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError as exc:
        raise RuntimeError(
            "ChromaDB is required for the Week 3 retrieval prototype. "
            "Install dependencies first, then rerun evaluation/retrieval_eval.py."
        ) from exc

    chunks = load_jsonl(CHUNKS_FILE)
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embedding_function = embedding_functions.DefaultEmbeddingFunction()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"description": "EGFR therapeutic strategy evidence chunks"},
    )
    collection.add(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )
    return collection


def run_eval(top_k: int = 5) -> dict:
    collection = build_collection()
    questions = load_jsonl(QUESTIONS_FILE)
    results = []

    for question in questions:
        response = collection.query(
            query_texts=[question["question"]],
            n_results=top_k,
        )
        documents = response["documents"][0]
        metadatas = response["metadatas"][0]
        ids = response["ids"][0]
        hit = hit_for_question(documents, question)
        results.append(
            {
                "question": question["question"],
                "expected_source": question["expected_source"],
                "category": question["category"],
                "hit": hit,
                "top_ids": ids,
                "top_drugs": [metadata.get("drug_name", "") for metadata in metadatas],
            }
        )

    hit_count = sum(1 for result in results if result["hit"])
    return {
        "question_count": len(questions),
        "hit_count": hit_count,
        "hit_rate": hit_count / len(questions) if questions else 0.0,
        "results": results,
    }


def main() -> None:
    summary = run_eval()
    RESULTS_FILE.write_text(json.dumps(summary, indent=2))
    print("Week 3 ChromaDB retrieval prototype")
    print("=" * 70)
    print("Questions:", summary["question_count"])
    print("Hits:", summary["hit_count"])
    print("Hit rate:", round(summary["hit_rate"], 3))
    print("Results file:", RESULTS_FILE)
    print()
    for result in summary["results"]:
        status = "HIT" if result["hit"] else "MISS"
        print(f"[{status}] {result['question']}")
        print("  expected:", result["expected_source"], "|", result["category"])
        print("  top drugs:", ", ".join(result["top_drugs"][:5]))


if __name__ == "__main__":
    main()
