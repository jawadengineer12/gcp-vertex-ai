from functools import lru_cache

from google import genai

from core.config import VERTEX_PROJECT, VERTEX_LOCATION
from core.logger import get_logger

LOGGER = get_logger(__name__)


@lru_cache(maxsize=1)
def get_vertex_client() -> genai.Client:
    """
    Instantiates and returns the Google GenAI client using Vertex AI.
    """
    LOGGER.info(
        "Initializing Vertex AI client | project=%s | location=%s",
        VERTEX_PROJECT,
        VERTEX_LOCATION,
    )

    return genai.Client(
        vertexai=True,
        project=VERTEX_PROJECT,
        location=VERTEX_LOCATION,
    )
