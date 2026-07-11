"""Compatibility entrypoint for running the FastAPI app."""

from app.main import app, create_app

__all__ = ["app", "create_app"]
