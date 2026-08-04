"""LLM answer generation for grounded therapeutic strategy responses."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def load_environment() -> None:
    """Load the nearest .env file from the project or parent folders."""
    current_path = Path(__file__).resolve()
    for parent in [current_path.parent, *current_path.parents]:
        env_path = parent / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
            return


load_environment()


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def estimate_openai_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost when token prices are configured through environment variables."""
    input_price = float(os.getenv("OPENAI_INPUT_PRICE_PER_1M", "0") or 0)
    output_price = float(os.getenv("OPENAI_OUTPUT_PRICE_PER_1M", "0") or 0)
    return ((prompt_tokens / 1_000_000) * input_price) + ((completion_tokens / 1_000_000) * output_price)


@dataclass(frozen=True)
class LLMAnswer:
    """Response from the answer-generation layer."""

    answer: str
    model: str
    used_llm: bool
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class LLMSummaryService:
    """Generate a grounded answer from a prepared RAG prompt.

    The service is deliberately conservative: if `OPENAI_API_KEY` is missing,
    it returns a clear fallback instead of failing. That keeps local retrieval
    and prompt engineering testable before API credentials are configured.
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY")

    def generate(self, system_prompt: str, user_prompt: str) -> LLMAnswer:
        if not self.api_key:
            return LLMAnswer(
                answer=(
                    "LLM answer generation was skipped because OPENAI_API_KEY is not set. "
                    "The retrieved evidence is available in the response, and the prompt was "
                    "built successfully. Set OPENAI_API_KEY to enable generated answers."
                ),
                model=self.model,
                used_llm=False,
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is required for LLM answer generation.") from exc

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        answer = response.choices[0].message.content or ""
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else prompt_tokens + completion_tokens
        return LLMAnswer(
            answer=answer.strip(),
            model=self.model,
            used_llm=True,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimate_openai_cost(prompt_tokens, completion_tokens),
        )
