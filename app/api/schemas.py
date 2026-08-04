"""Pydantic schemas for the Therapeutic Strategy Assistant API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    supported_targets: list[str]


class RetrieveRequest(BaseModel):
    question: str = Field(..., min_length=3)
    target_symbol: str | None = Field(default=None, description="Optional target filter, e.g. EGFR, KRAS, HER2.")
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievedChunkResponse(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any]
    distance: float | None = None


class RetrieveResponse(BaseModel):
    question: str
    target_filter: str | None
    retrieved_chunks: list[RetrievedChunkResponse]


class AskRequest(RetrieveRequest):
    include_prompt: bool = Field(default=False, description="Include the generated system/user prompt in the response.")


class AnswerEvaluationResponse(BaseModel):
    relevance: str
    explanation: str
    mode: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class AskResponse(BaseModel):
    conversation_id: str
    question: str
    answer: str
    model: str
    used_llm: bool
    target_filter: str | None
    retrieved_chunks: list[RetrievedChunkResponse]
    response_time: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    evaluation: AnswerEvaluationResponse
    prompt: dict[str, str] | None = None


class FeedbackRequest(BaseModel):
    conversation_id: str = Field(..., min_length=8)
    rating: int = Field(..., ge=-1, le=1, description="Use 1 for helpful, -1 for not helpful, or 0 for neutral.")
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    status: str
    conversation_id: str
    rating: int
