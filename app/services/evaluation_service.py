"""LLM-as-a-judge helpers for the therapeutic strategy RAG pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from app.services.llm_summary_service import DEFAULT_MODEL, estimate_openai_cost, load_environment


load_environment()

RELEVANT = "RELEVANT"
PARTLY_RELEVANT = "PARTLY_RELEVANT"
NON_RELEVANT = "NON_RELEVANT"
NOT_EVALUATED = "NOT_EVALUATED"
VALID_LABELS = {RELEVANT, PARTLY_RELEVANT, NON_RELEVANT}


@dataclass(frozen=True)
class AnswerEvaluation:
    """Evaluation result for one generated answer."""

    relevance: str
    explanation: str
    mode: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


def chunk_summary(chunks: list[Any], max_chars: int = 4000) -> str:
    lines = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata
        lines.append(
            "\n".join(
                [
                    f"[Evidence {index}]",
                    f"Target: {metadata.get('target_symbol', '')}",
                    f"Drug: {metadata.get('drug_name', '')}",
                    f"Source: {metadata.get('source', '')}",
                    str(chunk.text)[:800],
                ]
            )
        )
    return "\n\n".join(lines)[:max_chars]


def not_evaluated(explanation: str) -> AnswerEvaluation:
    return AnswerEvaluation(
        relevance=NOT_EVALUATED,
        explanation=explanation,
        mode="off",
    )


def llm_judge_answer(
    question: str,
    answer: str,
    chunks: list[Any],
    model: str = DEFAULT_MODEL,
) -> AnswerEvaluation:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return not_evaluated("OPENAI_API_KEY is not set, so the LLM judge was skipped.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is required for LLM answer evaluation.") from exc

    system_prompt = """
You are evaluating a biomedical research-support answer.

Use only the QUESTION, ANSWER, and RETRIEVED EVIDENCE.
Return JSON with two keys:
- relevance: one of RELEVANT, PARTLY_RELEVANT, NON_RELEVANT
- explanation: short reason for the label
""".strip()

    user_prompt = f"""
QUESTION:
{question}

ANSWER:
{answer}

RETRIEVED EVIDENCE:
{chunk_summary(chunks)}
""".strip()

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    text = response.choices[0].message.content or "{}"

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = {"relevance": PARTLY_RELEVANT, "explanation": text.strip()}

    relevance = str(payload.get("relevance", PARTLY_RELEVANT)).upper()
    if relevance not in VALID_LABELS:
        relevance = PARTLY_RELEVANT

    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else prompt_tokens + completion_tokens

    return AnswerEvaluation(
        relevance=relevance,
        explanation=str(payload.get("explanation", "")).strip(),
        mode="llm",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_openai_cost(prompt_tokens, completion_tokens),
    )


def evaluate_answer(question: str, answer: str, chunks: list[Any], used_llm: bool) -> AnswerEvaluation:
    mode = os.getenv("ANSWER_EVALUATION_MODE", "llm").lower().strip()

    if mode == "off":
        return not_evaluated("Answer evaluation is disabled.")

    if not used_llm:
        return not_evaluated("The answer-generation step was skipped, so there is no LLM answer to judge.")

    return llm_judge_answer(question=question, answer=answer, chunks=chunks)
