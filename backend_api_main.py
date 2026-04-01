"""Compatibility entrypoint for the FastAPI backend.

Use `backend.api.app:app` for the product package path. This module stays in
place so older scripts and local commands continue to work.
"""

from backend.api.app import OrchestratePayload, app

__all__ = ["app", "OrchestratePayload"]
