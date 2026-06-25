import json
import re
from pathlib import Path

import numpy as np
from numpy import dot
from numpy.linalg import norm

from core.config import (
    EMBEDDING_MODEL,
    WEIGHT_VECTOR,
    WEIGHT_BM25,
)
from core.vertex_client import get_vertex_client
from core.logger import get_logger
from services.vector_store import load_vector_store

LOGGER = get_logger(__name__)

STOPWORDS = {
    "a", "an", "the", "with", "and", "or", "to", "of", "on", "at",
    "using", "create", "make", "page", "one", "this", "is", "in",
    "for", "as", "by", "it", "that", "has", "have", "contains",
    "startx", "starty", "width", "height", "heith", "textbody",
    "formatting", "margins", "style", "fontfamily", "fontsize",
    "bold", "italic", "underline", "color", "autofit", "positions", "fit",
    "heith.", "texts", "aregiven",
}

BOOST_WORDS = {
    "cover": 10,
    "bleed": 8,
    "advertisement": 7,
    "ad": 7,
    "masthead": 7,
    "logo": 6,
    "article": 6,
    "text": 5,
    "image": 4,
    "images": 4,
    "pdf": 5,
    "background": 5,
    "full": 4,
    "large": 3,
    "font": 4,
    "black": 4,
    "size": 3,
    "columns": 5,
    "overlay": 6,
    "overlayed": 6,
    "overflow": 8,
    "continuation": 7,
    "negative": 5,
    "coordinates": 4,
    "pet": 6,
    "feature": 5,
}

PHRASE_BOOSTS = {
    "cover page": 10,
    "full bleed": 8,
    "full page": 6,
    "background image": 6,
    "masthead logo": 7,
    "image overlay": 5,
    "two text boxes": 6,
    "overflow continuation": 7,
    "feature story": 6,
    "pet of the month": 6,
}


vector_db = load_vector_store()
LOGGER.info("Vector store loaded | size=%s", len(vector_db))

# Pre-extract embeddings ONCE (no recomputation ever again)
library_embeddings = [
    np.array(item["embedding"])
    for item in vector_db
]

def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("coverpage", "cover page")
    text = text.replace("fullpage", "full page")
    text = text.replace("thefull", "the full")
    text = text.replace("overlayed", "overlay")
    return text


def tokenize(text: str) -> list[str]:
    text = normalize_text(text)
    words = re.findall(r"[a-zA-Z0-9#]+", text)
    return [word for word in words if word not in STOPWORDS]

# -----------------------------
# BM25-LIKE SCORE
# -----------------------------
def score_prompt(user_prompt: str, example_text: str) -> float:
    user_words = tokenize(user_prompt)
    example_words = set(tokenize(example_text))

    score = 0.0

    for w in user_words:
        if w in example_words:
            score += BOOST_WORDS.get(w, 1)

    user_lower = normalize_text(user_prompt)
    example_lower = normalize_text(example_text)

    for phrase, weight in PHRASE_BOOSTS.items():
        if phrase in user_lower and phrase in example_lower:
            score += weight

    return score


# -----------------------------
# COSINE SIMILARITY
# -----------------------------
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = norm(a) * norm(b)
    if denom == 0:
        return 0.0
    return float(dot(a, b) / denom)


# -----------------------------
# EMBED USER QUERY ONLY
# -----------------------------
def embed_text(text: str) -> np.ndarray:
    client = get_vertex_client()

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )

    return np.array(response.embeddings[0].values)


# -----------------------------
# HYBRID RETRIEVAL (FINAL FIXED)
# -----------------------------
def retrieve_hybrid_matches(user_prompt: str, top_k: int = 5) -> list[dict]:
    """
    Hybrid retrieval:
    - BM25-like lexical scoring
    - Precomputed vector embeddings (NO recomputation)
    - Weighted final ranking
    """

    LOGGER.info("Running hybrid retrieval | top_k=%s", top_k)

    # Embed ONLY user prompt
    user_embedding = embed_text(user_prompt)

    # BM25 scores
    raw_bm25 = [
        score_prompt(user_prompt, item["natural_language_intent"])
        for item in vector_db
    ]

    max_bm25 = max(raw_bm25) if raw_bm25 else 1.0

    scored = []

    for idx, item in enumerate(vector_db):
        bm25 = raw_bm25[idx] / max_bm25
        vector = cosine_similarity(user_embedding, library_embeddings[idx])

        final = (WEIGHT_VECTOR * vector) + (WEIGHT_BM25 * bm25)

        scored.append({
            "pageIndex": item["pageIndex"],
            "natural_language_intent": item["natural_language_intent"],
            "expected_layout_json": item["expected_layout_json"],
            "bm25_score": bm25,
            "vector_score": vector,
            "final_score": final,
        })

    scored.sort(key=lambda x: x["final_score"], reverse=True)

    top = scored[:top_k]

    LOGGER.info("Hybrid retrieval completed | returned=%s", len(top))

    for i, r in enumerate(top, 1):
        LOGGER.info(
            "Match | rank=%s | page=%s | final=%.4f | vec=%.4f | bm25=%.4f",
            i,
            r["pageIndex"],
            r["final_score"],
            r["vector_score"],
            r["bm25_score"],
        )

    return top
