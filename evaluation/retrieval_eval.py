"""Multi-target retrieval evaluation for the therapeutic strategy KB.

This script stays intentionally simple:
- read retrieval-ready chunks from data/processed
- index them in a local ChromaDB collection
- run multi-target evaluation questions
- report whether retrieved chunks match the expected target/source/category signal

No FastAPI, Streamlit, agent workflow, or LLM answer generation is used here.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.index_to_vectordb import (  # noqa: E402
    DEFAULT_CHUNKS_FILE,
    DEFAULT_COLLECTION_NAME,
    index_chunks,
)


QUESTIONS_FILE = PROJECT_ROOT / "evaluation" / "retrieval_questions_multi_target.jsonl"
RESULTS_FILE = PROJECT_ROOT / "evaluation" / "retrieval_results_multi_target.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")

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


def normalize_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def expected_terms(expected_source: str, category: str) -> list[str]:
    terms = []

    source_aliases = {
        "chembl": ["chembl", "mechanism", "max phase", "molecule id"],
        "openfda": ["openfda", "label", "indications"],
        "clinicaltrials.gov": ["clinical trial", "clinicaltrials", "trial"],
        "pubmed": ["pubmed", "literature"],
        "drugcentral": ["drugcentral", "indication", "activity"],
        "open targets": ["open targets", "disease associations"],
        "uniprot": ["uniprot", "protein"],
    }

    for part in expected_source.replace(";", "|").split("|"):
        source = normalize_text(part)
        if source:
            terms.extend(source_aliases.get(source, [source]))

    category_lower = normalize_text(category)
    if "approval" in category_lower:
        terms.extend(["approved", "max phase"])
    if "clinical" in category_lower:
        terms.extend(["clinical trial", "trial"])
    if "label" in category_lower:
        terms.extend(["openfda", "label", "indications"])
    if "literature" in category_lower:
        terms.extend(["pubmed"])
    if "mechanism" in category_lower:
        terms.extend(["mechanism", "action type"])
    if "indication" in category_lower:
        terms.extend(["indication", "drugcentral"])
    if "disease" in category_lower:
        terms.extend(["open targets", "disease associations"])
    if "evidence" in category_lower:
        terms.extend(["evidence summary", "project evidence strength"])

    return list(dict.fromkeys(term for term in terms if term))


def contains_any_text(documents: list[str], terms: list[str]) -> bool:
    combined = normalize_text("\n".join(documents))
    return any(normalize_text(term) in combined for term in terms)


def target_hit(metadatas: list[dict[str, Any]], expected_target: str) -> bool:
    expected = str(expected_target).upper()
    return any(str(metadata.get("target_symbol", "")).upper() == expected for metadata in metadatas)


def drug_is_named_in_question(question_text: str, expected_drugs: list[str]) -> bool:
    normalized_question = normalize_text(question_text)
    return any(normalize_text(drug) in normalized_question for drug in expected_drugs)


def drug_hit(question_text: str, metadatas: list[dict[str, Any]], expected_drugs: list[str]) -> bool:
    if not expected_drugs:
        return True

    # For broad questions such as "Which approved therapies target BRAF?",
    # expected_drugs are examples, not a hard requirement. For drug-specific
    # questions, the named drug should appear in the retrieved results.
    if not drug_is_named_in_question(question_text, expected_drugs):
        return True

    retrieved = {normalize_text(metadata.get("drug_name", "")) for metadata in metadatas}
    expected = {normalize_text(drug) for drug in expected_drugs}
    return bool(retrieved.intersection(expected))


def source_or_category_hit(documents: list[str], question: dict[str, Any]) -> bool:
    terms = expected_terms(question.get("expected_source", ""), question.get("category", ""))
    return contains_any_text(documents, terms)


def rerank_named_drug_matches(
    question: dict[str, Any],
    documents: list[str],
    metadatas: list[dict[str, Any]],
    ids: list[str],
    distances: list[float],
) -> tuple[list[str], list[dict[str, Any]], list[str], list[float]]:
    """Promote exact drug-name matches for drug-specific questions."""
    expected_drugs = question.get("expected_drugs", [])
    if not expected_drugs or not drug_is_named_in_question(question.get("question", ""), expected_drugs):
        return documents, metadatas, ids, distances

    expected = {normalize_text(drug) for drug in expected_drugs}
    rows = list(zip(documents, metadatas, ids, distances, strict=False))

    def rank_key(row: tuple[str, dict[str, Any], str, float]) -> tuple[int, float]:
        _, metadata, _, distance = row
        drug_name = normalize_text(metadata.get("drug_name", ""))
        exact_match = drug_name in expected
        return (0 if exact_match else 1, distance)

    rows = sorted(rows, key=rank_key)
    if not rows:
        return documents, metadatas, ids, distances

    reranked_documents, reranked_metadatas, reranked_ids, reranked_distances = zip(*rows, strict=False)
    return list(reranked_documents), list(reranked_metadatas), list(reranked_ids), list(reranked_distances)


def hit_for_question(documents: list[str], metadatas: list[dict[str, Any]], question: dict[str, Any]) -> bool:
    return (
        target_hit(metadatas, question.get("expected_target", ""))
        and drug_hit(question.get("question", ""), metadatas, question.get("expected_drugs", []))
        and source_or_category_hit(documents, question)
    )


def run_eval(
    questions_file: Path = QUESTIONS_FILE,
    chunks_file: Path = DEFAULT_CHUNKS_FILE,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    top_k: int = 10,
    use_target_filter: bool = True,
) -> dict[str, Any]:
    collection, chunks = index_chunks(
        chunks_file=chunks_file,
        collection_name=collection_name,
        reset=True,
    )
    questions = load_jsonl(questions_file)
    results = []

    indexed_targets = sorted({chunk.get("metadata", {}).get("target_symbol", "") for chunk in chunks})
    indexed_targets = [target for target in indexed_targets if target]

    for question in questions:
        where = None
        if use_target_filter and question.get("expected_target"):
            where = {"target_symbol": question["expected_target"]}

        candidate_k = max(top_k, 50)
        response = collection.query(
            query_texts=[question["question"]],
            n_results=candidate_k,
            where=where,
        )
        documents = response["documents"][0]
        metadatas = response["metadatas"][0]
        ids = response["ids"][0]
        distances = response.get("distances", [[]])[0]
        documents, metadatas, ids, distances = rerank_named_drug_matches(
            question=question,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            distances=distances,
        )
        documents = documents[:top_k]
        metadatas = metadatas[:top_k]
        ids = ids[:top_k]
        distances = distances[:top_k]
        hit = hit_for_question(documents, metadatas, question)

        results.append(
            {
                "question": question["question"],
                "expected_target": question.get("expected_target"),
                "expected_source": question.get("expected_source"),
                "category": question.get("category"),
                "expected_drugs": question.get("expected_drugs", []),
                "target_filter": where,
                "hit": hit,
                "top_ids": ids,
                "top_targets": [metadata.get("target_symbol", "") for metadata in metadatas],
                "top_drugs": [metadata.get("drug_name", "") for metadata in metadatas],
                "top_distances": distances,
            }
        )

    hit_count = sum(1 for result in results if result["hit"])
    questions_by_target = sorted({str(question.get("expected_target", "")) for question in questions if question.get("expected_target")})
    hits_by_target = {
        target: {
            "question_count": sum(1 for result in results if result["expected_target"] == target),
            "hit_count": sum(1 for result in results if result["expected_target"] == target and result["hit"]),
        }
        for target in questions_by_target
    }
    for target, values in hits_by_target.items():
        count = values["question_count"]
        values["hit_rate"] = values["hit_count"] / count if count else 0.0

    return {
        "chunks_file": str(chunks_file),
        "collection_name": collection_name,
        "use_target_filter": use_target_filter,
        "indexed_chunk_count": len(chunks),
        "indexed_targets": indexed_targets,
        "question_count": len(questions),
        "hit_count": hit_count,
        "hit_rate": hit_count / len(questions) if questions else 0.0,
        "hits_by_target": hits_by_target,
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate multi-target ChromaDB retrieval.")
    parser.add_argument("--questions-file", type=Path, default=QUESTIONS_FILE)
    parser.add_argument("--chunks-file", type=Path, default=DEFAULT_CHUNKS_FILE)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--results-file", type=Path, default=RESULTS_FILE)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--no-target-filter", action="store_true", help="Disable target_symbol filters during evaluation.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_eval(
        questions_file=args.questions_file,
        chunks_file=args.chunks_file,
        collection_name=args.collection_name,
        top_k=args.top_k,
        use_target_filter=not args.no_target_filter,
    )
    args.results_file.write_text(json.dumps(summary, indent=2))

    print("Multi-target ChromaDB retrieval evaluation")
    print("=" * 70)
    print("Chunks indexed:", summary["indexed_chunk_count"])
    print("Targets indexed:", ", ".join(summary["indexed_targets"]))
    print("Target filter:", "enabled" if summary["use_target_filter"] else "disabled")
    print("Questions:", summary["question_count"])
    print("Hits:", summary["hit_count"])
    print("Hit rate:", round(summary["hit_rate"], 3))
    print("Results file:", args.results_file)
    print()

    print("Target coverage:")
    for target, values in summary["hits_by_target"].items():
        print(f"  {target}: {values['hit_count']}/{values['question_count']} ({values['hit_rate']:.3f})")
    print()

    for result in summary["results"]:
        status = "HIT" if result["hit"] else "MISS"
        print(f"[{status}] {result['question']}")
        print("  expected:", result["expected_target"], "|", result["expected_source"], "|", result["category"])
        print("  top targets:", ", ".join(result["top_targets"][:5]))
        print("  top drugs:", ", ".join(result["top_drugs"][:5]))


if __name__ == "__main__":
    main()
