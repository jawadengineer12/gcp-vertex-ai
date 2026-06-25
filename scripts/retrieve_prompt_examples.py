import json

from core.config import UPDATED_LIBRARY_PATH
from core.logger import setup_logging, get_logger
from services.retrieval_service import load_library, find_top_matches

setup_logging()
LOGGER = get_logger(__name__)

TOP_K = 3


def main() -> None:
    LOGGER.info("Keyword retrieval script started.")

    user_prompt = input("Enter your natural language prompt: ")

    if not user_prompt.strip():
        LOGGER.warning("Empty prompt received.")
        print("Prompt cannot be empty.")
        return

    LOGGER.info("User prompt received | length=%s", len(user_prompt))

    library = load_library(UPDATED_LIBRARY_PATH)

    matches = find_top_matches(
        user_prompt=user_prompt,
        library=library,
        top_k=TOP_K,
    )

    LOGGER.info("Keyword retrieval completed | matches=%s", len(matches))

    print("\nUSER PROMPT:")
    print(user_prompt)

    print("\nTOP MATCHES:")

    for idx, match in enumerate(matches, start=1):
        LOGGER.info(
            "Keyword match | rank=%s | pageIndex=%s | score=%.4f",
            idx,
            match.get("pageIndex"),
            match.get("score", 0.0),
        )

        print("\n" + "=" * 80)
        print(f"RANK: {idx}")
        print(f"SCORE: {match['score']:.4f}")
        print(f"PAGE INDEX: {match['pageIndex']}")

        print("\nMATCHED NATURAL LANGUAGE INTENT:")
        print(match["natural_language_intent"])

        print("\nEXPECTED LAYOUT JSON:")
        print(json.dumps(match["expected_layout_json"], indent=2))

    LOGGER.info("Keyword retrieval script completed.")


if __name__ == "__main__":
    main()
