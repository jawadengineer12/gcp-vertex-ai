# services/reranker_service.py
import logging
from sentence_transformers import CrossEncoder
from config.config import AppConfig

logger = logging.getLogger(__name__)


class RerankerService:
    """
    Wraps a CrossEncoder model for deep-attention reranking.
    Model is loaded once on first instantiation and kept warm in memory.
    """

    def __init__(self) -> None:
        logger.info("Loading reranker model: %s",
                    AppConfig.RERANKER_MODEL_NAME)
        self.model = CrossEncoder(AppConfig.RERANKER_MODEL_NAME)
        logger.info("Reranker model loaded.")

    def rerank_candidates(self, user_prompt: str, candidates: list[dict]) -> list[dict]:
        """
        Reranks a list of candidates using the CrossEncoder.
        Attaches 'rerank_score' to each candidate dict and returns sorted list.
        """
        if not candidates:
            logger.warning("Reranker called with empty candidate list.")
            return []

        pairs = [
            (user_prompt, candidate["natural_language_intent"])
            for candidate in candidates
        ]

        scores = self.model.predict(pairs)

        for idx, candidate in enumerate(candidates):
            candidate["rerank_score"] = float(scores[idx])

        reranked = sorted(
            candidates, key=lambda x: x["rerank_score"], reverse=True)
        logger.info("Reranking complete | input=%d | output=%d",
                    len(candidates), len(reranked))
        return reranked


def rerank_matches(user_prompt: str, top_k_candidates: list[dict]) -> list[dict]:
    """
    Module-level convenience function for scripts that don't use the class directly.
    Creates a temporary RerankerService instance and reranks the candidates.
    """
    service = RerankerService()
    return service.rerank_candidates(user_prompt, top_k_candidates)
