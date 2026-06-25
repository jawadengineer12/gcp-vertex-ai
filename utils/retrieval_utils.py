from sentence_transformers import CrossEncoder
import json
import re
from pathlib import Path

TOP_K = 3

# Expanded to strip recurring database technical parameters
STOPWORDS = {
    "a", "an", "the", "with", "and", "or", "to", "of", "on", "at",
    "using", "create", "make", "page", "one", "this", "is", "in",
    "for", "as", "by", "it", "that", "has", "have", "contains",
    # Added layout boilerplate parameters to stop inflation
    "startx", "starty", "width", "height", "heith", "textbody",
    "formatting", "margins", "style", "fontfamily", "fontsize",
    "bold", "italic", "underline", "color", "autofit", "positions", "fit",
    "width", "height", "heith", "heith.", "textbody", "texts", "aregiven"
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


def load_library(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Library file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("coverpage", "cover page")
    text = text.replace("fullpage", "full page")
    text = text.replace("thefull", "the full")
    text = text.replace("overlayed", "overlay")
    return text


def tokenize(text: str):
    text = normalize_text(text)
    words = re.findall(r"[a-zA-Z0-9#]+", text)
    return [word for word in words if word not in STOPWORDS]


def score_prompt(user_prompt: str, example_text: str) -> float:
    """
    Returns an UN-CLAMPED raw keyword + phrase boost score.
    Normalization is now handled dynamically across the entire pipeline.
    """
    user_words = tokenize(user_prompt)
    example_words = set(tokenize(example_text))

    score = 0
    for word in user_words:
        if word in example_words:
            score += BOOST_WORDS.get(word, 1)

    user_lower = normalize_text(user_prompt)
    example_lower = normalize_text(example_text)

    for phrase, weight in PHRASE_BOOSTS.items():
        if phrase in user_lower and phrase in example_lower:
            score += weight

    return float(score)


def find_top_matches(user_prompt: str, library: list, top_k: int = TOP_K):
    scored_items = []

    # Calculate raw scores first
    raw_scores = []
    for item in library:
        intent = item.get("natural_language_intent", "")
        raw_scores.append((item, score_prompt(user_prompt, intent)))

    # Dynamically find the relative max ceiling for this specific query run
    max_raw = max([s[1] for s in raw_scores]) if raw_scores else 0
    max_divisor = max_raw if max_raw > 0 else 1.0

    for item, raw_score in raw_scores:
        intent = item.get("natural_language_intent", "")
        # Scale smoothly between 0.0 and 1.0 relative to the best keyword match
        normalized_score = raw_score / max_divisor

        scored_items.append({
            "score": normalized_score,
            "pageIndex": item.get("pageIndex"),
            "natural_language_intent": intent,
            "expected_layout_json": item.get("expected_layout_json"),
        })

    scored_items.sort(key=lambda x: x["score"], reverse=True)
    return scored_items[:top_k]


# Load a highly-optimized, lightweight reranking model
# (This downloads once and runs instantly on your local CPU)
print("Loading Reranker Model...")
reranker_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')


def rerank_matches(user_prompt: str, top_k_candidates: list) -> list:
    """
    Takes the Top-K candidates from the Hybrid Search and reranks them
    using a deep-attention Cross-Encoder.
    """
    # 1. Prepare the pairs for the Cross-Encoder
    # Format: [(User Prompt, Candidate Intent 1), (User Prompt, Candidate Intent 2), ...]
    pairs = [
        (user_prompt, candidate['natural_language_intent'])
        for candidate in top_k_candidates
    ]

    # 2. Score the pairs
    # The model outputs a list of float scores representing semantic relevance
    scores = reranker_model.predict(pairs)

    # 3. Attach the new reranked scores to the candidates
    for idx, candidate in enumerate(top_k_candidates):
        candidate['rerank_score'] = float(scores[idx])

    # 4. Sort the candidates by the new rerank score (highest to lowest)
    reranked_candidates = sorted(
        top_k_candidates, key=lambda x: x['rerank_score'], reverse=True)

    return reranked_candidates

# --- EXAMPLE INTEGRATION ---
# Assuming `hybrid_matches` is the Top 10 list from your current hybrid_retrieval_scoring.py
# top_10_hybrid = find_top_matches(user_prompt, library, top_k=10)
# final_top_3 = rerank_matches(user_prompt, top_10_hybrid)[:3]
