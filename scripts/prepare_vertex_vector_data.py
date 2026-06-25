import json
from pathlib import Path
from google import genai

# -------------------------------
# CONFIG
# -------------------------------
LIBRARY_PATH = Path("normalized_data/layout_prompt_library_updated.json")
OUTPUT_PATH = Path("normalized_data/vertex_index_data.jsonl")


def main():
    print("🚀 Initializing Vertex AI Embedding Client...")
    # Initialize your enterprise client
    client = genai.Client(
        vertexai=True,
        project="indesign-layout-ai",
        location="us-central1"
    )
    embedding_model = "text-embedding-004"

    # 1. Load the existing prompt library
    print(f"📂 Loading library from {LIBRARY_PATH}...")
    with open(LIBRARY_PATH, "r", encoding="utf-8") as f:
        library = json.load(f)

    # 2. Extract intents for batch embedding
    intents = [item['natural_language_intent'] for item in library]

    # 3. Generate embeddings for the entire library (Doing this ONCE)
    print(f"🧠 Generating embeddings for {len(intents)} items...")
    response = client.models.embed_content(
        model=embedding_model,
        contents=intents
    )

    # 4. Write to Vertex AI required JSONL format
    print(f"✍️ Writing Vertex AI Vector Search file to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as out_file:
        for idx, item in enumerate(library):
            # We use the pageIndex as the unique ID for the Vector Search
            vector_id = str(item['pageIndex'])
            embedding_values = response.embeddings[idx].values

            # Create the exact JSON schema Vertex Vector Search requires
            vertex_record = {
                "id": vector_id,
                "embedding": embedding_values
            }
            # Write as a single line JSON (JSONL)
            out_file.write(json.dumps(vertex_record) + "\n")

    print("✅ Success! Your data is ready to be uploaded to Google Cloud Storage.")


if __name__ == "__main__":
    main()
