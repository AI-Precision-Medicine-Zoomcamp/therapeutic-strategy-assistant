"""FastAPI routes for retrieval and local RAG answers."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    AskRequest,
    AskResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    RetrieveRequest,
    RetrieveResponse,
    RetrievedChunkResponse,
)
from app.rag_pipeline import SUPPORTED_TARGETS, answer_question, retrieve_chunks
from monitoring.telemetry import log_feedback, log_interaction


router = APIRouter()


def chunk_to_response(chunk) -> RetrievedChunkResponse:
    return RetrievedChunkResponse(
        id=chunk.id,
        text=chunk.text,
        metadata=chunk.metadata,
        distance=chunk.distance,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="therapeutic-strategy-assistant",
        supported_targets=sorted(SUPPORTED_TARGETS),
    )


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(request: RetrieveRequest) -> RetrieveResponse:
    try:
        chunks = retrieve_chunks(
            question=request.question,
            target_symbol=request.target_symbol,
            top_k=request.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    target_filter = request.target_symbol.upper() if request.target_symbol else None
    if target_filter == "HER2":
        target_filter = "ERBB2"

    return RetrieveResponse(
        question=request.question,
        target_filter=target_filter,
        retrieved_chunks=[chunk_to_response(chunk) for chunk in chunks],
    )


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    try:
        response = answer_question(
            question=request.question,
            target_symbol=request.target_symbol,
            top_k=request.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        log_interaction(response, source="api")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to save conversation: {exc}") from exc

    return AskResponse(
        conversation_id=response.conversation_id,
        question=response.question,
        answer=response.answer,
        model=response.model,
        used_llm=response.used_llm,
        target_filter=response.target_filter,
        retrieved_chunks=[chunk_to_response(chunk) for chunk in response.retrieved_chunks],
        response_time=response.response_time,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_tokens=response.total_tokens,
        estimated_cost_usd=response.estimated_cost_usd,
        evaluation=asdict(response.evaluation),
        prompt=response.prompt if request.include_prompt else None,
    )


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(request: FeedbackRequest) -> FeedbackResponse:
    try:
        log_feedback(
            conversation_id=request.conversation_id,
            rating=request.rating,
            comment=request.comment,
            source="api",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to save feedback: {exc}") from exc

    return FeedbackResponse(
        status="saved",
        conversation_id=request.conversation_id,
        rating=request.rating,
    )
