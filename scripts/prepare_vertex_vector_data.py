# scripts/prepare_vertex_vector_data.py
"""
Generates embeddings for every prompt library entry and writes them
in Vertex AI Vector Search JSONL format.

Output format (one JSON object per line):
    {"id": "<stable_id>", "embedding": [0.1, 0.2, ...]}

The 'id' field matches the stable IDs stored in the prompt library,
so Vector Search results can be looked up directly in the library.

Run this script whenever the prompt library is updated.
"""
import json
import numpy as np
from pathlib import Path

from config.config import AppConfig
from core.logger import setup_logging, get_logger
from core.vertex_client import get_vertex_client
from utils.retrieval_utils import build_stable_id

setup_logging()
logger = get_logger(__name__)


def normalize_vector(embedding: list[float]) -> list[float]:
    """Normalize a vector to unit length (L2 norm) for cosine distance."""
    vec = np.array(embedding)
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm > 0 else vec.tolist()


def main() -> None:
    logger.info("Prepare Vertex vector data script started.")

    library_path = AppConfig.PROMPT_LIBRARY_PATH
    output_path = AppConfig.VERTEX_INDEX_DATA_PATH

    if not library_path.exists():
        raise FileNotFoundError(f"Prompt library not found: {library_path}")

    with open(library_path, "r", encoding="utf-8") as f:
        library: list[dict] = json.load(f)

    logger.info("Loaded library | records=%d", len(library))

    # Assign stable IDs to any entries that don't have one yet
    updated = False
    for idx, item in enumerate(library):
        if "id" not in item or not item["id"]:
            item["id"] = build_stable_id(item, idx)
            updated = True

    if updated:
        logger.info("Assigned stable IDs to library entries without IDs.")
        with open(library_path, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2)
        logger.info("Updated library saved with stable IDs: %s", library_path)

    intents = [item["natural_language_intent"] for item in library]

    logger.info("Generating embeddings | model=%s | count=%d",
                AppConfig.EMBEDDING_MODEL, len(intents))
    print(f"🧠 Generating embeddings for {len(intents)} items...")

    client = get_vertex_client()
    response = client.models.embed_content(
        model=AppConfig.EMBEDDING_MODEL,
        contents=intents,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with open(output_path, "w", encoding="utf-8") as out_file:
        for idx, item in enumerate(library):
            stable_id = item["id"]
            normalized_embedding = normalize_vector(
                response.embeddings[idx].values)

            # Vertex AI Vector Search required JSONL format
            vertex_record = {
                "id": stable_id,
                "embedding": normalized_embedding,
            }
            out_file.write(json.dumps(vertex_record) + "\n")
            written += 1

    logger.info(
        "JSONL written | path=%s | records=%d", output_path, written
    )
    print(f"✅ Success! {written} records written to: {output_path}")
    print("Next step: upload this file to GCS and rebuild/update the index.")


if __name__ == "__main__":
    main()
