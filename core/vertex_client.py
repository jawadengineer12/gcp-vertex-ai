"""Lazy, container-scoped Vertex GenAI client."""

from functools import cache

from google import genai

from core.config import AppConfig


@cache
def get_vertex_client() -> genai.Client:
    """Create the shared client only when the paid pipeline starts."""
    AppConfig.validate_vertex_config()
    return genai.Client(
        vertexai=True,
        project=AppConfig.PROJECT_ID,
        location=AppConfig.LOCATION,
    )
