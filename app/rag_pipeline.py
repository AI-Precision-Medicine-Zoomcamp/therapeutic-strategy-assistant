"""Local RAG pipeline for the multi-target therapeutic strategy assistant."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.llm_summary_service import LLMSummaryService  # noqa: E402
from ingestion.index_to_vectordb import (  # noqa: E402
    DEFAULT_COLLECTION_NAME,
    get_chroma_collection,
    index_chunks,
)


PROMPTS_FILE = PROJECT_ROOT / "prompts" / "system_prompts.yaml"
SUPPORTED_TARGETS = {"EGFR", "ERBB2", "BRAF", "ALK", "KRAS", "VEGFA", "MET", "PIK3CA"}


DEFAULT_SYSTEM_PROMPT = """You are a biomedical research-support assistant.
Use only retrieved evidence. Do not provide medical advice. Mention sources and evidence gaps."""

DEFAULT_USER_TEMPLATE = """Question:
{question}

Retrieved evidence:
{context}

Write a grounded research-support answer using only the retrieved evidence."""


@dataclass(frozen=True)
class RetrievedChunk:
    """A retrieved evidence chunk."""

    id: str
    text: str
    metadata: dict[str, Any]
    distance: float | None = None


@dataclass(frozen=True)
class RAGResponse:
    """Complete local RAG response."""

    question: str
    answer: str
    model: str
    used_llm: bool
    target_filter: str | None
    retrieved_chunks: list[RetrievedChunk]
    prompt: dict[str, str]


def normalize_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def load_prompt_block(name: str, default: str) -> str:
    """Read a simple YAML block scalar from prompts/system_prompts.yaml."""
    if not PROMPTS_FILE.exists():
        return default

    lines = PROMPTS_FILE.read_text().splitlines()
    start_index = None
    prefix = f"{name}: |"
    for index, line in enumerate(lines):
        if line.strip() == prefix:
            start_index = index + 1
            break

    if start_index is None:
        return default

    block_lines = []
    for line in lines[start_index:]:
        if line and not line.startswith(" ") and line.endswith(": |"):
            break
        if line.startswith("  "):
            block_lines.append(line[2:])
        elif not line.strip():
            block_lines.append("")
        else:
            break
    return "\n".join(block_lines).strip() or default


def validate_target(target_symbol: str | None) -> str | None:
    if target_symbol is None or not str(target_symbol).strip():
        return None
    normalized = str(target_symbol).upper().strip()
    if normalized == "HER2":
        normalized = "ERBB2"
    if normalized not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported target '{target_symbol}'. Supported targets: {sorted(SUPPORTED_TARGETS)}")
    return normalized


def ensure_collection(collection_name: str = DEFAULT_COLLECTION_NAME):
    """Load the Chroma collection, building it if needed."""
    collection = get_chroma_collection(collection_name=collection_name, reset=False)
    try:
        count = collection.count()
    except Exception:
        count = 0
    if count == 0:
        collection, _ = index_chunks(collection_name=collection_name, reset=True)
    return collection


def extract_named_drugs(question: str, metadatas: list[dict[str, Any]]) -> set[str]:
    normalized_question = normalize_text(question)
    names = set()
    for metadata in metadatas:
        drug_name = str(metadata.get("drug_name", ""))
        if drug_name and normalize_text(drug_name) in normalized_question:
            names.add(normalize_text(drug_name))
    return names


def rerank_named_drugs(question: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    named_drugs = extract_named_drugs(question, [chunk.metadata for chunk in chunks])
    if not named_drugs:
        return chunks

    def rank_key(chunk: RetrievedChunk) -> tuple[int, float]:
        drug_name = normalize_text(chunk.metadata.get("drug_name", ""))
        exact_match = drug_name in named_drugs
        return (0 if exact_match else 1, chunk.distance if chunk.distance is not None else 999.0)

    return sorted(chunks, key=rank_key)


def retrieve_chunks(
    question: str,
    target_symbol: str | None = None,
    top_k: int = 5,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> list[RetrievedChunk]:
    """Retrieve evidence chunks from ChromaDB."""
    target = validate_target(target_symbol)
    collection = ensure_collection(collection_name=collection_name)
    where = {"target_symbol": target} if target else None
    candidate_k = max(top_k, 50)
    response = collection.query(query_texts=[question], n_results=candidate_k, where=where)

    ids = response["ids"][0]
    documents = response["documents"][0]
    metadatas = response["metadatas"][0]
    distances = response.get("distances", [[]])[0]

    chunks = [
        RetrievedChunk(id=chunk_id, text=text, metadata=metadata, distance=distance)
        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances, strict=False)
    ]
    chunks = rerank_named_drugs(question, chunks)
    return chunks[:top_k]


def build_context(chunks: list[RetrievedChunk], max_chars_per_chunk: int = 1800) -> str:
    """Format retrieved chunks into compact prompt context."""
    parts = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata
        text = chunk.text[:max_chars_per_chunk].strip()
        parts.append(
            "\n".join(
                [
                    f"[Evidence {index}]",
                    f"Target: {metadata.get('target_symbol', '')}",
                    f"Drug: {metadata.get('drug_name', '')}",
                    f"Evidence strength: {metadata.get('evidence_strength', '')}",
                    f"Evidence score: {metadata.get('evidence_score', '')}",
                    f"Chunk ID: {chunk.id}",
                    text,
                ]
            )
        )
    return "\n\n".join(parts)


def build_prompts(question: str, chunks: list[RetrievedChunk]) -> dict[str, str]:
    system_prompt = load_prompt_block("rag_answer_system", DEFAULT_SYSTEM_PROMPT)
    user_template = load_prompt_block("rag_answer_user_template", DEFAULT_USER_TEMPLATE)
    context = build_context(chunks)
    return {
        "system": system_prompt,
        "user": user_template.format(question=question, context=context),
    }


def fallback_evidence_answer(question: str, chunks: list[RetrievedChunk], llm_message: str) -> str:
    """Return a useful answer when no API key is configured."""
    lines = [
        llm_message,
        "",
        "Retrieved evidence summary:",
    ]
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata
        lines.append(
            f"{index}. {metadata.get('target_symbol', '')} - {metadata.get('drug_name', '')}: "
            f"{metadata.get('evidence_strength', '')} evidence, score={metadata.get('evidence_score', '')}."
        )
    lines.extend(
        [
            "",
            "Research-only note: this output summarizes retrieved evidence and is not medical advice.",
        ]
    )
    return "\n".join(lines)


def answer_question(
    question: str,
    target_symbol: str | None = None,
    top_k: int = 5,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> RAGResponse:
    """Retrieve context and generate a grounded answer."""
    chunks = retrieve_chunks(
        question=question,
        target_symbol=target_symbol,
        top_k=top_k,
        collection_name=collection_name,
    )
    prompts = build_prompts(question, chunks)
    llm_service = LLMSummaryService()
    llm_answer = llm_service.generate(system_prompt=prompts["system"], user_prompt=prompts["user"])
    answer = llm_answer.answer
    if not llm_answer.used_llm:
        answer = fallback_evidence_answer(question, chunks, llm_answer.answer)

    return RAGResponse(
        question=question,
        answer=answer,
        model=llm_answer.model,
        used_llm=llm_answer.used_llm,
        target_filter=validate_target(target_symbol),
        retrieved_chunks=chunks,
        prompt=prompts,
    )


def response_to_dict(response: RAGResponse, include_prompt: bool = False) -> dict[str, Any]:
    payload = asdict(response)
    if not include_prompt:
        payload.pop("prompt", None)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local multi-target RAG query.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--target", default=None, help="Optional target filter, e.g. EGFR, KRAS, HER2.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--include-prompt", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    response = answer_question(question=args.question, target_symbol=args.target, top_k=args.top_k)
    print(json.dumps(response_to_dict(response, include_prompt=args.include_prompt), indent=2))


if __name__ == "__main__":
    main()
