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


class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    used_llm: bool
    target_filter: str | None
    retrieved_chunks: list[RetrievedChunkResponse]
    prompt: dict[str, str] | None = None
