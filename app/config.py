"""Shared project paths and runtime settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"


def load_environment() -> None:
    """Load the nearest .env file from the project or parent folders."""
    for parent in [PROJECT_ROOT, *PROJECT_ROOT.parents]:
        env_path = parent / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
            return


load_environment()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
ANSWER_EVALUATION_MODE = os.getenv("ANSWER_EVALUATION_MODE", "llm")
