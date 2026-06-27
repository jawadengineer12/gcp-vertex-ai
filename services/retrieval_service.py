# services/retrieval_service.py
"""
Hybrid retrieval service: Vertex AI Vector Search + BM25 lexical scoring.

Pipeline:
  1. Embed user query via Vertex AI.
  2. Retrieve vector candidates from Vertex AI Vector Search.
  3. Retrieve BM25 candidates from the full local prompt library.
  4. Normalize both score sets independently.
  5. Merge candidates by stable unique ID.
  6. Combine scores with configurable weights.
  7. Sort and return top merged candidates for reranking.
"""
import logging
from pathlib import Path

from config.config import AppConfig
from core.vertex_client import vertex_client
from services.vector_store import VertexVectorStore
from utils.retrieval_utils import (
    load_library,
    score_prompt,
    find_top_matches,
    build_stable_id,
)

logger = logging.getLogger(__name__)


class RetrievalService:
    """
    Executes the full hybrid retrieval pipeline and returns context candidates
    ready for reranking.
    """

    def __init__(self) -> None:
        self.vector_store = VertexVectorStore()
        self.library = self._load_library(AppConfig.PROMPT_LIBRARY_PATH)
        # Build a fast ID → item lookup map
        self._id_map: dict[str, dict] = {
            item.get("id", build_stable_id(item, idx)): item
            for idx, item in enumerate(self.library)
        }
        logger.info(
            "RetrievalService initialized | library_size=%d", len(self.library)
        )

    def _load_library(self, path: Path) -> list:
        return load_library(path)

    # ── Public entry point ────────────────────────────────────────────────────

    def execute_pipeline(self, user_prompt: str) -> dict:
        """
        Runs the full hybrid retrieval pipeline.

        Returns a dict with all intermediate stages for run tracing:
        {
            "vector_candidates": [...],
            "bm25_candidates":   [...],
            "merged_candidates": [...],
        }
        """
        # 1. Embed user query
        logger.info("Generating query embedding.")
        embedding_response = vertex_client.models.embed_content(
            model=AppConfig.EMBEDDING_MODEL,
            contents=[user_prompt],
        )
        query_embedding = embedding_response.embeddings[0].values

        # 2. Vector candidates
        vector_candidates = self._get_vector_candidates(query_embedding)

        # 3. BM25 candidates
        bm25_candidates = self._get_bm25_candidates(user_prompt)

        # 4. Merge
        merged_candidates = self._merge_candidates(
            vector_candidates, bm25_candidates)

        return {
            "vector_candidates": vector_candidates,
            "bm25_candidates": bm25_candidates,
            "merged_candidates": merged_candidates,
        }

    # ── Stage: Vector retrieval ───────────────────────────────────────────────

    def _get_vector_candidates(self, query_embedding: list[float]) -> list[dict]:
        """Fetch top-K candidates from Vertex AI Vector Search."""
        logger.info(
            "Querying Vertex AI Vector Search | top_k=%d", AppConfig.TOP_K_VECTOR
        )
        candidate_ids = self.vector_store.find_nearest_neighbors(
            query_embedding, k=AppConfig.TOP_K_VECTOR
        )

        if not candidate_ids:
            logger.warning("Vector Search returned zero candidates.")
            return []

        candidates = []
        for rank, cid in enumerate(candidate_ids):
            item = self._id_map.get(cid)
            if item is None:
                logger.warning(
                    "Vector Search returned ID not found in library: %s", cid
                )
                continue
            # Score: rank-based (1.0 for rank 0, decaying)
            vector_score = 1.0 - (rank / max(len(candidate_ids), 1))
            candidates.append({
                "id": cid,
                "pageIndex": item.get("pageIndex"),
                "natural_language_intent": item.get("natural_language_intent", ""),
                "expected_layout_json": item.get("expected_layout_json"),
                "vector_score": vector_score,
                "bm25_score": 0.0,
                "final_score": 0.0,
            })

        logger.info("Vector candidates hydrated | count=%d", len(candidates))
        return candidates

    # ── Stage: BM25 retrieval ─────────────────────────────────────────────────

    def _get_bm25_candidates(self, user_prompt: str) -> list[dict]:
        """Score the full library with BM25 and return top-K."""
        logger.info(
            "Running BM25 lexical scoring | top_k=%d", AppConfig.TOP_K_BM25
        )
        raw_scores = []
        for idx, item in enumerate(self.library):
            intent = item.get("natural_language_intent", "")
            raw = score_prompt(user_prompt, intent)
            raw_scores.append((idx, item, raw))

        max_raw = max((r[2] for r in raw_scores), default=0)
        max_divisor = max_raw if max_raw > 0 else 1.0

        candidates = []
        for idx, item, raw in raw_scores:
            bm25_score = raw / max_divisor
            item_id = item.get("id", build_stable_id(item, idx))
            candidates.append({
                "id": item_id,
                "pageIndex": item.get("pageIndex"),
                "natural_language_intent": item.get("natural_language_intent", ""),
                "expected_layout_json": item.get("expected_layout_json"),
                "vector_score": 0.0,
                "bm25_score": bm25_score,
                "final_score": 0.0,
            })

        candidates.sort(key=lambda x: x["bm25_score"], reverse=True)
        top = candidates[: AppConfig.TOP_K_BM25]

        if not top or top[0]["bm25_score"] == 0.0:
            logger.warning(
                "BM25 returned zero-score candidates for this query.")

        logger.info("BM25 candidates | count=%d", len(top))
        return top

    # ── Stage: Merge ──────────────────────────────────────────────────────────

    def _merge_candidates(
        self,
        vector_candidates: list[dict],
        bm25_candidates: list[dict],
    ) -> list[dict]:
        """
        Merge vector and BM25 candidates by stable ID.
        Combine scores using configurable weights.
        """
        if not vector_candidates and not bm25_candidates:
            raise RuntimeError(
                "Both vector and BM25 retrieval returned zero candidates. "
                "Cannot proceed. Check your prompt library, index, and query."
            )

        merged: dict[str, dict] = {}

        for c in vector_candidates:
            cid = c["id"]
            merged[cid] = {**c}

        for c in bm25_candidates:
            cid = c["id"]
            if cid in merged:
                merged[cid]["bm25_score"] = c["bm25_score"]
            else:
                merged[cid] = {**c}

        vw = AppConfig.VECTOR_WEIGHT
        bw = AppConfig.BM25_WEIGHT

        for cid, c in merged.items():
            c["final_score"] = vw * c["vector_score"] + bw * c["bm25_score"]

        result = sorted(merged.values(),
                        key=lambda x: x["final_score"], reverse=True)
        result = result[: AppConfig.TOP_K_MERGED]

        logger.info(
            "Merge complete | vector=%d | bm25=%d | merged=%d | weights=(v=%.2f, b=%.2f)",
            len(vector_candidates),
            len(bm25_candidates),
            len(result),
            vw,
            bw,
        )
        return result


# ── Module-level convenience function (for standalone scripts) ────────────────

def load_library(path: Path) -> list:
    """Re-exported for scripts that import directly from this module."""
    from utils.retrieval_utils import load_library as _load
    return _load(path)


def retrieve_hybrid_matches(
    user_prompt: str,
    library: list,
    top_k: int = 10,
) -> list[dict]:
    """
    Standalone hybrid scorer for scripts (no Vertex Vector Search).
    Uses only BM25 over a supplied library list.
    Useful for local testing or the hybrid_retrieval_scoring.py script.
    """
    from utils.retrieval_utils import score_prompt, build_stable_id

    raw_scores = []
    for idx, item in enumerate(library):
        intent = item.get("natural_language_intent", "")
        raw = score_prompt(user_prompt, intent)
        raw_scores.append((idx, item, raw))

    max_raw = max((r[2] for r in raw_scores), default=0)
    max_divisor = max_raw if max_raw > 0 else 1.0

    candidates = []
    for idx, item, raw in raw_scores:
        bm25_score = raw / max_divisor
        item_id = item.get("id", build_stable_id(item, idx))
        candidates.append({
            "id": item_id,
            "pageIndex": item.get("pageIndex"),
            "natural_language_intent": item.get("natural_language_intent", ""),
            "expected_layout_json": item.get("expected_layout_json"),
            "bm25_score": bm25_score,
            "vector_score": 0.0,
            "final_score": bm25_score,
        })

    candidates.sort(key=lambda x: x["final_score"], reverse=True)
    return candidates[:top_k]


def find_top_matches(user_prompt: str, library: list, top_k: int = 3) -> list[dict]:
    """Re-exported alias for scripts that import find_top_matches from this module."""
    from utils.retrieval_utils import find_top_matches as _ftm
    return _ftm(user_prompt, library, top_k)
