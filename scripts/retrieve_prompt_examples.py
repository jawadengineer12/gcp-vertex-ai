# scripts/retrieve_prompt_examples.py
"""
Standalone script for testing pure BM25/keyword retrieval locally.
No Vertex Vector Search is used — useful for fast local testing.
"""
import json
from config.config import UPDATED_LIBRARY_PATH
from core.logger import setup_logging, get_logger
from services.retrieval_service import load_library, find_top_matches

setup_logging()
logger = get_logger(__name__)

TOP_K = 3


def main() -> None:
    logger.info("Keyword retrieval script started.")

    user_prompt = input("Enter your natural language prompt: ").strip()
    if not user_prompt:
        print("Prompt cannot be empty.")
        return

    logger.info("Prompt | length=%d", len(user_prompt))

    library = load_library(UPDATED_LIBRARY_PATH)
    matches = find_top_matches(
        user_prompt=user_prompt, library=library, top_k=TOP_K)

    print("\nUSER PROMPT:")
    print(user_prompt)
    print("\nTOP MATCHES:")

    for idx, match in enumerate(matches, start=1):
        print("\n" + "=" * 80)
        print(f"RANK: {idx}")
        print(f"SCORE     : {match['score']:.4f}")
        print(f"PAGE INDEX: {match['pageIndex']}")
        print(f"ID        : {match.get('id')}")
        print("\nMATCHED NATURAL LANGUAGE INTENT:")
        print(match["natural_language_intent"])
        print("\nEXPECTED LAYOUT JSON:")
        print(json.dumps(match["expected_layout_json"], indent=2))

    logger.info("Keyword retrieval script complete.")


if __name__ == "__main__":
    main()
