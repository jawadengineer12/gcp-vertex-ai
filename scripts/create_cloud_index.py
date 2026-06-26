# scripts/create_cloud_index.py
"""
Creates a new Vertex AI Vector Search index from a GCS bucket.
Run this once after uploading vertex_index_data.jsonl to GCS.

NOTE: Index creation takes 15–30 minutes. The script prints the index ID
when provisioning begins — save it for your .env / deployment config.
"""
from google.cloud import aiplatform
from config.config import AppConfig
from core.logger import setup_logging, get_logger
from google.cloud import aiplatform
from google.cloud.aiplatform.matching_engine import MatchingEngineIndexConfig

setup_logging()
logger = get_logger(__name__)

DIMENSIONS = 768  # text-embedding-004 output dimension


def main() -> None:
    logger.info("Create cloud index script started.")
    logger.info("Project: %s | Location: %s",
                AppConfig.PROJECT_ID, AppConfig.LOCATION)
    logger.info("GCS bucket URI: %s", AppConfig.GCS_VECTOR_BUCKET_URI)

    print("🚀 Initializing Google Cloud Platform connection...")
    aiplatform.init(project=AppConfig.PROJECT_ID, location=AppConfig.LOCATION)

    print("\n⏳ Creating Vertex AI Vector Search Index...")
    print("⚠️  NOTE: This runs in the background and can take 15–30 minutes.")

    my_index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name="layout-rag-index-test",
        contents_delta_uri=AppConfig.GCS_VECTOR_BUCKET_URI,
        dimensions=DIMENSIONS,
        approximate_neighbors_count=10,
        distance_measure_type="COSINE_DISTANCE",
    )

    logger.info("Index created | name=%s", my_index.name)
    print(f"\n✅ SUCCESS! Vector Search Index created.")
    print(f"Index resource name: {my_index.name}")
    print("\nSave this value — you will need it to deploy an index endpoint.")


if __name__ == "__main__":
    main()
