from functools import lru_cache

from sentence_transformers import CrossEncoder

from core.config import RERANKER_MODEL
from core.logger import get_logger

LOGGER = get_logger(__name__)


@lru_cache(maxsize=1)
def get_reranker_model() -> CrossEncoder:
    LOGGER.info("Loading reranker model | model=%s", RERANKER_MODEL)
    model = CrossEncoder(RERANKER_MODEL)
    LOGGER.info("Reranker model loaded successfully.")
    return model


def rerank_matches(user_prompt: str, top_k_candidates: list[dict]) -> list[dict]:
    LOGGER.info("Running reranker | candidates=%s", len(top_k_candidates))

    if not top_k_candidates:
        LOGGER.warning("No candidates provided to reranker.")
        return []

    pairs = [
        (user_prompt, candidate["natural_language_intent"])
        for candidate in top_k_candidates
    ]

    model = get_reranker_model()
    scores = model.predict(pairs)

    reranked_candidates = []

    for idx, candidate in enumerate(top_k_candidates):
        enriched_candidate = dict(candidate)
        enriched_candidate["rerank_score"] = float(scores[idx])
        reranked_candidates.append(enriched_candidate)

    reranked_candidates.sort(
        key=lambda x: x["rerank_score"],
        reverse=True,
    )

    LOGGER.info("Reranking completed.")

    for rank, match in enumerate(reranked_candidates, start=1):
        LOGGER.info(
            "Reranked match | rank=%s | pageIndex=%s | rerank_score=%.4f | final_score=%.4f",
            rank,
            match.get("pageIndex"),
            match.get("rerank_score", 0.0),
            match.get("final_score", 0.0),
        )

    return reranked_candidates
