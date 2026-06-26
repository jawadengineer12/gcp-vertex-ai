# scripts/hybrid_retrieval_scoring.py
"""
Standalone script for testing hybrid BM25 + vector scoring locally.
Uses the module-level convenience functions (no Vertex Vector Search call).
"""
from config.config import AppConfig, UPDATED_LIBRARY_PATH, STAGE_1_TOP_K
from core.logger import setup_logging, get_logger
from services.retrieval_service import load_library, retrieve_hybrid_matches
from services.reranker_service import rerank_matches

setup_logging()
logger = get_logger(__name__)


def print_candidates(title: str, candidates: list[dict]) -> None:
    print(f"\n{title}")
    for idx, c in enumerate(candidates, start=1):
        print("\n" + "=" * 80)
        print(f"RANK: {idx}")
        print(f"FINAL SCORE : {c.get('final_score', 0.0):.4f}")
        print(f"BM25 SCORE  : {c.get('bm25_score', 0.0):.4f}")
        print(f"VECTOR SCORE: {c.get('vector_score', 0.0):.4f}")
        if "rerank_score" in c:
            print(f"RERANK SCORE: {c['rerank_score']:.4f}")
        print(f"PAGE INDEX  : {c.get('pageIndex')}")
        print(f"ID          : {c.get('id')}")
        print("\nMATCHED NATURAL LANGUAGE INTENT:")
        print(c.get("natural_language_intent", ""))


def main() -> None:
    logger.info("Hybrid retrieval scoring script started.")

    user_prompt = input("Enter your natural language prompt: ").strip()
    if not user_prompt:
        print("Prompt cannot be empty.")
        return

    logger.info("User prompt | length=%d", len(user_prompt))

    library = load_library(UPDATED_LIBRARY_PATH)
    logger.info("Library loaded | records=%d", len(library))

    top_candidates = retrieve_hybrid_matches(
        user_prompt=user_prompt,
        library=library,
        top_k=STAGE_1_TOP_K,
    )
    logger.info("Hybrid candidates | count=%d", len(top_candidates))

    reranked = rerank_matches(user_prompt=user_prompt,
                              top_k_candidates=top_candidates)
    logger.info("Reranked candidates | count=%d", len(reranked))

    print_candidates("▸ Top Hybrid Candidates (BM25)", top_candidates)
    print_candidates("▸ Reranked Candidates (CrossEncoder)", reranked)
    logger.info("Script complete.")


if __name__ == "__main__":
    main()
