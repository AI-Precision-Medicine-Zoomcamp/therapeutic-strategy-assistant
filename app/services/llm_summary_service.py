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


@dataclass(frozen=True)
class LLMAnswer:
    """Response from the answer-generation layer."""

    answer: str
    model: str
    used_llm: bool


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
        return LLMAnswer(answer=answer.strip(), model=self.model, used_llm=True)
