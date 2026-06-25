import json
from pathlib import Path
import numpy as np
from numpy import dot
from numpy.linalg import norm

from utils.retrieval_utils import load_library, score_prompt, rerank_matches
from google import genai
from google.genai import types

# -------------------------------
# CONFIG
# -------------------------------
LIBRARY_PATH = Path("normalized_data/layout_prompt_library_updated.json")
TOP_K = 5
WEIGHT_VECTOR = 0.7
WEIGHT_BM25 = 0.3

# -------------------------------
# UTILS
# -------------------------------


def cosine_similarity(a, b):
    # Ensure inputs are standard numpy arrays for rapid matrix arithmetic
    return dot(a, b) / (norm(a) * norm(b))


# -------------------------------
# LOAD LIBRARY
# -------------------------------
library = load_library(LIBRARY_PATH)

# -------------------------------
# VERTEX AI EMBEDDING CLIENT
# -------------------------------
# Correct client initialization for Vertex AI models in google-genai
embedding_client = genai.Client(
    vertexai=True,
    project="indesign-layout-ai",
    location="us-central1"
)
embedding_model = "text-embedding-004"

# -------------------------------
# GET USER PROMPT
# -------------------------------
user_prompt = input("Enter your natural language prompt: ")

# Generate embedding for user prompt using correct SDK syntax
user_response = embedding_client.models.embed_content(
    model=embedding_model,
    contents=user_prompt
)
user_embedding = np.array(user_response.embeddings[0].values)

# -------------------------------
# BATCHED LIBRARY EMBEDDINGS (Performance Fix)
# -------------------------------
# Batch-fetch all intents at once to respect API token constraints and prevent lag
intents = [example['natural_language_intent'] for example in library]

print(f"Generating embeddings for {len(intents)} library entries...")
library_response = embedding_client.models.embed_content(
    model=embedding_model,
    contents=intents
)
# Map vector dimensions cleanly to match array positions
library_embeddings = [np.array(e.values) for e in library_response.embeddings]

# -------------------------------
# COMPUTE SCORES (Updated Loop Section)
# -------------------------------
scored_entries = []

# First pass: Get all raw token scores
raw_bm25_scores = [score_prompt(
    user_prompt, ex['natural_language_intent']) for ex in library]
max_bm25_ceil = max(raw_bm25_scores) if max(raw_bm25_scores) > 0 else 1.0

for idx, example in enumerate(library):
    # Dynamic 0.0 to 1.0 keyword normalization based on max run capacity
    bm25_score = raw_bm25_scores[idx] / max_bm25_ceil

    # Extract embedding value arrays
    example_embedding = library_embeddings[idx]
    vector_score = cosine_similarity(user_embedding, example_embedding)

    # Hybrid weighted calculation remains clean
    final_score = WEIGHT_VECTOR * vector_score + WEIGHT_BM25 * bm25_score


    scored_entries.append({
        "pageIndex": example['pageIndex'],
        "natural_language_intent": example['natural_language_intent'],
        "expected_layout_json": example['expected_layout_json'],
        "bm25_score": bm25_score,
        "vector_score": vector_score,
        "final_score": final_score
    })

# -------------------------------
# SORT TOP RESULTS
# -------------------------------
top_candidates = sorted(
    scored_entries, key=lambda x: x['final_score'], reverse=True)[:TOP_K]
reranked_candidates = rerank_matches(user_prompt, top_candidates)
# -------------------------------
# DISPLAY RESULTS
# -------------------------------
print("Top Candidates")
for idx, match in enumerate(top_candidates, start=1):
    print("\n" + "="*80)
    print(f"RANK: {idx}")
    print(f"FINAL SCORE: {match['final_score']:.4f}")
    print(f"BM25 SCORE: {match['bm25_score']:.4f}")
    print(f"VECTOR SCORE: {match['vector_score']:.4f}")
    print(f"PAGE INDEX: {match['pageIndex']}")
    print("\nMATCHED NATURAL LANGUAGE INTENT:")
    print(match['natural_language_intent'])
    
    
    
print("Reranked Candidates")
for idx, match in enumerate(reranked_candidates, start=1):
    print("\n" + "="*80)
    print(f"RANK: {idx}")
    print(f"FINAL SCORE: {match['final_score']:.4f}")
    print(f"BM25 SCORE: {match['bm25_score']:.4f}")
    print(f"VECTOR SCORE: {match['vector_score']:.4f}")
    print(f"PAGE INDEX: {match['pageIndex']}")
    print("\nMATCHED NATURAL LANGUAGE INTENT:")
    print(match['natural_language_intent'])
