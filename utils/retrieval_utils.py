# utils/retrieval_utils.py
"""
BM25-style lexical scoring utilities.
These functions are the source-of-truth for keyword/phrase matching
and are shared by both the retrieval service and standalone scripts.
"""
import re
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Stopwords ─────────────────────────────────────────────────────────────────
STOPWORDS = {
    "a", "an", "the", "with", "and", "or", "to", "of", "on", "at",
    "using", "create", "make", "page", "one", "this", "is", "in",
    "for", "as", "by", "it", "that", "has", "have", "contains",
    "startx", "starty", "width", "height", "heith", "textbody",
    "formatting", "margins", "style", "fontfamily", "fontsize",
    "bold", "italic", "underline", "color", "autofit", "positions", "fit",
    "texts", "aregiven",
}

# ── Token boost weights ───────────────────────────────────────────────────────
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

# ── Phrase boost weights ──────────────────────────────────────────────────────
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
    return [w for w in words if w not in STOPWORDS]


def score_prompt(user_prompt: str, example_text: str) -> float:
    """
    Returns an un-clamped raw keyword + phrase boost score.
    Normalization is handled dynamically across the full candidate set.
    """
    user_words = tokenize(user_prompt)
    example_words = set(tokenize(example_text))

    score = 0.0
    for word in user_words:
        if word in example_words:
            score += BOOST_WORDS.get(word, 1)

    user_lower = normalize_text(user_prompt)
    example_lower = normalize_text(example_text)

    for phrase, weight in PHRASE_BOOSTS.items():
        if phrase in user_lower and phrase in example_lower:
            score += weight

    return score


def find_top_matches(user_prompt: str, library: list, top_k: int = 3) -> list[dict]:
    """
    Pure BM25-style lexical scoring over the full library.
    Returns top_k scored items sorted by normalized score descending.
    """
    raw_scores = []
    for item in library:
        intent = item.get("natural_language_intent", "")
        raw_scores.append((item, score_prompt(user_prompt, intent)))

    max_raw = max((s[1] for s in raw_scores), default=0)
    max_divisor = max_raw if max_raw > 0 else 1.0

    scored_items = []
    for item, raw_score in raw_scores:
        intent = item.get("natural_language_intent", "")
        normalized_score = raw_score / max_divisor
        scored_items.append({
            "id": item.get("id", str(item.get("pageIndex", ""))),
            "score": normalized_score,
            "bm25_score": normalized_score,
            "pageIndex": item.get("pageIndex"),
            "natural_language_intent": intent,
            "expected_layout_json": item.get("expected_layout_json"),
        })

    scored_items.sort(key=lambda x: x["score"], reverse=True)
    return scored_items[:top_k]


def load_library(path: Path) -> list:
    if not path.exists():
        raise FileNotFoundError(f"Prompt library not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_stable_id(item: dict, example_index: int) -> str:
    """
    Builds a globally unique stable ID for a prompt library entry.
    Format: projectName_pageIndex_exampleIndex
    Falls back gracefully if projectName is absent.
    """
    project_name = (
        item.get("expected_layout_json", {})
            .get("projectInfo", {})
            .get("projectName", "example")
    )
    page_index = item.get("pageIndex", 0)
    # Sanitize project name for use as an ID component
    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", str(project_name)).lower()
    return f"{safe_name}_{page_index}_{example_index}"
