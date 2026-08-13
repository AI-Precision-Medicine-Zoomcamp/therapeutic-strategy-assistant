"""Compare answer-generation prompts with the existing RAG judge."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag_pipeline import (  # noqa: E402
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_TEMPLATE,
    build_context,
    load_prompt_block,
    retrieve_chunks,
)
from app.services.evaluation_service import evaluate_answer  # noqa: E402
from app.services.llm_summary_service import DEFAULT_MODEL, LLMSummaryService  # noqa: E402
from evaluation.retrieval_eval import QUESTIONS_FILE, load_jsonl  # noqa: E402


RESULTS_FILE = PROJECT_ROOT / "evaluation" / "llm_evaluation_results.json"


def prompt_variants() -> dict[str, dict[str, str]]:
    standard_system_prompt = load_prompt_block("rag_answer_system", DEFAULT_SYSTEM_PROMPT)
    standard_user_template = load_prompt_block("rag_answer_user_template", DEFAULT_USER_TEMPLATE)

    structured_system_prompt = """You are a biomedical research-support assistant.
Use only retrieved evidence. Do not provide medical advice.
Write a concise answer with these sections:
Direct answer
Evidence
Evidence gaps
Research-only note""".strip()

    return {
        "standard_prompt": {
            "system": standard_system_prompt,
            "user_template": standard_user_template,
        },
        "structured_prompt": {
            "system": structured_system_prompt,
            "user_template": standard_user_template,
        },
    }


def format_user_prompt(question: str, chunks: list[Any], user_template: str) -> str:
    context = build_context(chunks)
    return user_template.format(question=question, context=context)


def evaluate_prompt_variant(
    name: str,
    prompt_config: dict[str, str],
    questions: list[dict[str, Any]],
    top_k: int,
    model: str,
) -> dict[str, Any]:
    llm_service = LLMSummaryService(model=model)
    rows = []

    for question_row in questions:
        question = question_row["question"]
        target = question_row.get("expected_target")
        chunks = retrieve_chunks(question=question, target_symbol=target, top_k=top_k)
        user_prompt = format_user_prompt(question, chunks, prompt_config["user_template"])

        started_at = time.perf_counter()
        llm_answer = llm_service.generate(
            system_prompt=prompt_config["system"],
            user_prompt=user_prompt,
        )
        answer_eval = evaluate_answer(
            question=question,
            answer=llm_answer.answer,
            chunks=chunks,
            used_llm=llm_answer.used_llm,
        )
        response_time = time.perf_counter() - started_at

        rows.append(
            {
                "question": question,
                "expected_target": target,
                "approach": name,
                "answer": llm_answer.answer,
                "used_llm": llm_answer.used_llm,
                "relevance": answer_eval.relevance,
                "relevance_explanation": answer_eval.explanation,
                "prompt_tokens": llm_answer.prompt_tokens,
                "completion_tokens": llm_answer.completion_tokens,
                "total_tokens": llm_answer.total_tokens,
                "estimated_cost_usd": llm_answer.estimated_cost_usd + answer_eval.estimated_cost_usd,
                "response_time": response_time,
            }
        )

    label_counts = Counter(row["relevance"] for row in rows)
    total_cost = sum(row["estimated_cost_usd"] for row in rows)
    total_tokens = sum(row["total_tokens"] for row in rows)
    avg_response_time = sum(row["response_time"] for row in rows) / len(rows) if rows else 0.0

    return {
        "approach": name,
        "question_count": len(rows),
        "label_counts": dict(label_counts),
        "relevant_count": label_counts.get("RELEVANT", 0),
        "partly_relevant_count": label_counts.get("PARTLY_RELEVANT", 0),
        "non_relevant_count": label_counts.get("NON_RELEVANT", 0),
        "not_evaluated_count": label_counts.get("NOT_EVALUATED", 0),
        "avg_response_time": avg_response_time,
        "total_tokens": total_tokens,
        "estimated_cost_usd": total_cost,
        "results": rows,
    }


def compare_answer_prompts(
    questions_file: Path = QUESTIONS_FILE,
    limit: int = 4,
    top_k: int = 5,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    questions = load_jsonl(questions_file)[:limit]
    summaries = [
        evaluate_prompt_variant(name, prompt_config, questions, top_k=top_k, model=model)
        for name, prompt_config in prompt_variants().items()
    ]

    if all(summary["not_evaluated_count"] == summary["question_count"] for summary in summaries):
        best_approach = None
    else:
        best = max(
            summaries,
            key=lambda item: (
                item["relevant_count"],
                item["partly_relevant_count"],
                -item["estimated_cost_usd"],
            ),
        )
        best_approach = best["approach"]

    return {
        "model": model,
        "top_k": top_k,
        "question_count": len(questions),
        "best_approach": best_approach,
        "approaches": summaries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare RAG answer prompt approaches.")
    parser.add_argument("--questions-file", type=Path, default=QUESTIONS_FILE)
    parser.add_argument("--results-file", type=Path, default=RESULTS_FILE)
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comparison = compare_answer_prompts(
        questions_file=args.questions_file,
        limit=args.limit,
        top_k=args.top_k,
        model=args.model,
    )
    args.results_file.write_text(json.dumps(comparison, indent=2))

    print("RAG answer prompt comparison")
    print("=" * 70)
    print("Model:", comparison["model"])
    print("Questions:", comparison["question_count"])
    print("Best approach:", comparison["best_approach"] or "not selected because LLM evaluation did not run")
    for summary in comparison["approaches"]:
        print(
            f"{summary['approach']}: "
            f"RELEVANT={summary['relevant_count']}, "
            f"PARTLY_RELEVANT={summary['partly_relevant_count']}, "
            f"NON_RELEVANT={summary['non_relevant_count']}, "
            f"cost=${summary['estimated_cost_usd']:.6f}"
        )
    print("Results file:", args.results_file)


if __name__ == "__main__":
    main()
