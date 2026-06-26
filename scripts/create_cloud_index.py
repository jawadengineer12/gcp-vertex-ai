from google.cloud import aiplatform

# --- CONFIGURATION ---
PROJECT_ID = "project-df3ee720-da3e-4aa4-863"
REGION = "us-central1"
BUCKET_URI = "gs://layout-rag-data"  # Where your .jsonl file lives
DIMENSIONS = 768  # The exact dimension size for text-embedding-004


def main():
    print("🚀 Initializing Google Cloud Platform connection...")
    aiplatform.init(project=PROJECT_ID, location=REGION)

    print("\n⏳ Creating Vertex AI Vector Search Index...")
    print("⚠️  NOTE: Google is now provisioning dedicated ScaNN hardware.")
    print("⚠️  This process runs in the background and can take 15 to 30 minutes. Please do not close the script.")

    # Create the Index directly from the bucket
    my_index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name="layout-rag-index",
        contents_delta_uri=BUCKET_URI,
        dimensions=DIMENSIONS,
        approximate_neighbors_count=10,
        distance_measure_type="COSINE_DISTANCE",
    )

    print("\n✅ SUCCESS! Your Vector Search Index is built.")
    print(f"Index ID: {my_index.name}")


if __name__ == "__main__":
    main()
