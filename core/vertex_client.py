# core/vertex_client.py
from google import genai
from config.config import AppConfig

# Module-level singleton — initialized once, reused everywhere.
vertex_client = genai.Client(
    vertexai=True,
    project=AppConfig.PROJECT_ID,
    location=AppConfig.LOCATION,
)


def get_vertex_client() -> genai.Client:
    """
    Returns the shared Vertex AI GenAI client singleton.
    Use this factory import in scripts that need an explicit function call.
    """
    return vertex_client
