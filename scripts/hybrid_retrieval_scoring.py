from core.config import UPDATED_LIBRARY_PATH, STAGE_1_TOP_K
from core.logger import setup_logging, get_logger
from services.retrieval_service import load_library, retrieve_hybrid_matches
from services.reranker_service import rerank_matches

setup_logging()
LOGGER = get_logger(__name__)


def print_candidates(title: str, candidates: list[dict]) -> None:
    print(f"\n{title}")

    for idx, match in enumerate(candidates, start=1):
        print("\n" + "=" * 80)
        print(f"RANK: {idx}")
        print(f"FINAL SCORE: {match.get('final_score', 0.0):.4f}")
        print(f"BM25 SCORE: {match.get('bm25_score', 0.0):.4f}")
        print(f"VECTOR SCORE: {match.get('vector_score', 0.0):.4f}")

        if "rerank_score" in match:
            print(f"RERANK SCORE: {match['rerank_score']:.4f}")

        print(f"PAGE INDEX: {match.get('pageIndex')}")

        print("\nMATCHED NATURAL LANGUAGE INTENT:")
        print(match.get("natural_language_intent", ""))


def main() -> None:
    LOGGER.info("Hybrid retrieval scoring script started.")

    user_prompt = input("Enter your natural language prompt: ")

    if not user_prompt.strip():
        LOGGER.warning("Empty prompt received.")
        print("Prompt cannot be empty.")
        return

    LOGGER.info("User prompt received | length=%s", len(user_prompt))

    library = load_library(UPDATED_LIBRARY_PATH)

    top_candidates = retrieve_hybrid_matches(
        user_prompt=user_prompt,
        library=library,
        top_k=STAGE_1_TOP_K,
    )

    LOGGER.info("Hybrid candidates returned | count=%s", len(top_candidates))

    reranked_candidates = rerank_matches(
        user_prompt=user_prompt,
        top_k_candidates=top_candidates,
    )

    LOGGER.info("Reranked candidates returned | count=%s",
                len(reranked_candidates))

    print_candidates("Top Hybrid Candidates", top_candidates)
    print_candidates("Reranked Candidates", reranked_candidates)

    LOGGER.info("Hybrid retrieval scoring script completed.")


if __name__ == "__main__":
    main()
