import json

from core.config import UPDATED_LIBRARY_PATH, VERTEX_INDEX_PATH, EMBEDDING_MODEL
from core.logger import setup_logging, get_logger
from core.vertex_client import get_vertex_client

setup_logging()
LOGGER = get_logger(__name__)


def main() -> None:
    LOGGER.info("Prepare Vertex vector data script started.")

    if not UPDATED_LIBRARY_PATH.exists():
        raise FileNotFoundError(UPDATED_LIBRARY_PATH)

    client = get_vertex_client()

    with open(UPDATED_LIBRARY_PATH, "r", encoding="utf-8") as f:
        library = json.load(f)

    LOGGER.info("Loaded library | records=%s", len(library))

    intents = [item["natural_language_intent"] for item in library]

    LOGGER.info("Generating embeddings | count=%s", len(intents))

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=intents,
    )

    # -----------------------------
    # BUILD CLEAN JSON STRUCTURE
    # -----------------------------
    vector_db = []

    for idx, item in enumerate(library):
        vector_db.append({
            "pageIndex": item["pageIndex"],
            "natural_language_intent": item["natural_language_intent"],
            "expected_layout_json": item["expected_layout_json"],
            "embedding": response.embeddings[idx].values
        })

    # -----------------------------
    # WRITE VALID JSON ARRAY
    # -----------------------------
    VERTEX_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(VERTEX_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(vector_db, f, indent=2)

    LOGGER.info("Vector DB written successfully | path=%s", VERTEX_INDEX_PATH)

    print(f"✅ Success: {VERTEX_INDEX_PATH}")


if __name__ == "__main__":
    main()
