"""Compatibility entrypoint for running the FastAPI app as `app.api:app`."""

from app.main import app, create_app

__all__ = ["app", "create_app"]
