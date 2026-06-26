# scripts/update_vector_index.py
"""
Upserts new or updated datapoints into an existing Vertex AI Vector Search index.

Use this script when you add new examples to the prompt library
without wanting to rebuild the entire index from scratch.

Workflow:
  1. Add new examples to prompt library JSON.
  2. Run prepare_vertex_vector_data.py to regenerate the full JSONL.
  3. Run this script to upsert only the new/changed datapoints.

The script reads the JSONL file and upserts all records.
Vertex AI handles deduplication by ID — existing IDs are updated,
new IDs are inserted.
"""
import json
from google.cloud import aiplatform
from google.cloud.aiplatform_v1 import IndexServiceClient
from google.cloud.aiplatform_v1.types import index as index_types
from config.config import AppConfig
from core.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main() -> None:
    logger.info("Update vector index script started.")

    jsonl_path = AppConfig.VERTEX_INDEX_DATA_PATH
    if not jsonl_path.exists():
        raise FileNotFoundError(
            f"JSONL file not found: {jsonl_path}. "
            f"Run prepare_vertex_vector_data.py first."
        )

    # Load all datapoints from JSONL
    datapoints = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            datapoints.append(
                index_types.IndexDatapoint(
                    datapoint_id=record["id"],
                    feature_vector=record["embedding"],
                )
            )

    logger.info("Loaded datapoints from JSONL | count=%d", len(datapoints))
    print(f"📦 Loaded {len(datapoints)} datapoints from {jsonl_path}")

    # Extract index ID from the full resource name stored in INDEX_ENDPOINT
    # INDEX_ENDPOINT format: projects/{num}/locations/{loc}/indexEndpoints/{id}
    # Index resource name is separate — derive from DEPLOYED_INDEX_ID config
    # Users must set VERTEX_INDEX_RESOURCE_NAME in .env for upsert.
    import os
    index_resource_name = os.getenv("VERTEX_INDEX_RESOURCE_NAME")
    if not index_resource_name:
        raise EnvironmentError(
            "VERTEX_INDEX_RESOURCE_NAME is required for upsert. "
            "Set it in your .env file. "
            "Format: projects/{project_number}/locations/{location}/indexes/{index_id}"
        )

    aiplatform.init(project=AppConfig.PROJECT_ID, location=AppConfig.LOCATION)

    api_endpoint = f"{AppConfig.LOCATION}-aiplatform.googleapis.com"
    client = IndexServiceClient(client_options={"api_endpoint": api_endpoint})

    # Upsert in batches of 100 (Vertex AI limit per request)
    batch_size = 100
    total_upserted = 0

    for i in range(0, len(datapoints), batch_size):
        batch = datapoints[i: i + batch_size]
        client.upsert_datapoints(
            request=index_types.UpsertDatapointsRequest(
                index=index_resource_name,
                datapoints=batch,
            )
        )
        total_upserted += len(batch)
        logger.info(
            "Upserted batch | batch_start=%d | batch_size=%d | total=%d",
            i, len(batch), total_upserted,
        )
        print(f"  ✓ Upserted records {i + 1}–{i + len(batch)}")

    logger.info("Upsert complete | total=%d", total_upserted)
    print(f"\n✅ Done. {total_upserted} datapoints upserted into index.")
    print("The index will update in the background (usually within a few minutes).")


if __name__ == "__main__":
    main()
