"""PostgreSQL monitoring helpers for the capstone RAG app.

This follows the course monitoring pattern: save each conversation and each
user feedback event into database tables, then read those tables from dashboards.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_environment() -> None:
    """Load the nearest .env file from the project or parent folders."""
    for parent in [PROJECT_ROOT, *PROJECT_ROOT.parents]:
        env_path = parent / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
            return


load_environment()


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_db_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.getenv("POSTGRES_DB", "therapeutic_strategy"),
        user=os.getenv("POSTGRES_USER", "user"),
        password=os.getenv("POSTGRES_PASSWORD", "password"),
    )


def init_db(drop: bool = False) -> None:
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            if drop:
                cur.execute("DROP TABLE IF EXISTS feedback")
                cur.execute("DROP TABLE IF EXISTS conversations")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    model TEXT NOT NULL,
                    used_llm BOOLEAN NOT NULL,
                    target_filter TEXT,
                    retrieved_chunk_ids TEXT NOT NULL,
                    prompt_system TEXT NOT NULL,
                    prompt_user TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    response_time FLOAT NOT NULL,
                    estimated_cost_usd FLOAT NOT NULL,
                    evaluation_relevance TEXT NOT NULL,
                    evaluation_explanation TEXT NOT NULL,
                    evaluation_mode TEXT NOT NULL,
                    evaluation_prompt_tokens INTEGER NOT NULL,
                    evaluation_completion_tokens INTEGER NOT NULL,
                    evaluation_total_tokens INTEGER NOT NULL,
                    evaluation_cost_usd FLOAT NOT NULL,
                    source TEXT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    conversation_id TEXT REFERENCES conversations(conversation_id),
                    rating INTEGER NOT NULL,
                    comment TEXT,
                    source TEXT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
                )
                """
            )

        conn.commit()

    finally:
        conn.close()


def to_plain_data(value: Any) -> Any:
    if is_dataclass(value):
        return to_plain_data(asdict(value))
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    return value


def log_interaction(response: Any, source: str = "api") -> None:
    payload = to_plain_data(response)
    evaluation = payload["evaluation"]
    prompt = payload["prompt"]

    retrieved_chunk_ids = [chunk["id"] for chunk in payload["retrieved_chunks"]]

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (
                    conversation_id,
                    question,
                    answer,
                    model,
                    used_llm,
                    target_filter,
                    retrieved_chunk_ids,
                    prompt_system,
                    prompt_user,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    response_time,
                    estimated_cost_usd,
                    evaluation_relevance,
                    evaluation_explanation,
                    evaluation_mode,
                    evaluation_prompt_tokens,
                    evaluation_completion_tokens,
                    evaluation_total_tokens,
                    evaluation_cost_usd,
                    source,
                    timestamp
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (conversation_id) DO NOTHING
                """,
                (
                    payload["conversation_id"],
                    payload["question"],
                    payload["answer"],
                    payload["model"],
                    payload["used_llm"],
                    payload["target_filter"],
                    json.dumps(retrieved_chunk_ids),
                    prompt.get("system", ""),
                    prompt.get("user", ""),
                    payload["prompt_tokens"],
                    payload["completion_tokens"],
                    payload["total_tokens"],
                    payload["response_time"],
                    payload["estimated_cost_usd"],
                    evaluation["relevance"],
                    evaluation["explanation"],
                    evaluation["mode"],
                    evaluation["prompt_tokens"],
                    evaluation["completion_tokens"],
                    evaluation["total_tokens"],
                    evaluation["estimated_cost_usd"],
                    source,
                    utc_now(),
                ),
            )

        conn.commit()

    finally:
        conn.close()


def log_feedback(conversation_id: str, rating: int, comment: str | None = None, source: str = "api") -> None:
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (
                    conversation_id,
                    rating,
                    comment,
                    source,
                    timestamp
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    conversation_id,
                    rating,
                    comment or "",
                    source,
                    utc_now(),
                ),
            )

        conn.commit()

    finally:
        conn.close()


def monitoring_summary() -> dict[str, Any]:
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), COALESCE(SUM(estimated_cost_usd), 0), COALESCE(AVG(response_time), 0) FROM conversations")
            conversation_count, total_cost, avg_response_time = cur.fetchone()

            cur.execute("SELECT COUNT(*) FROM feedback")
            feedback_count = cur.fetchone()[0]

        return {
            "conversations": conversation_count,
            "feedback": feedback_count,
            "total_estimated_cost_usd": float(total_cost),
            "avg_response_time": float(avg_response_time),
        }

    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized")
