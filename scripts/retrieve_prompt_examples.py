import json
import sys
from pathlib import Path

from utils.retrieval_utils import load_library, find_top_matches


LIBRARY_PATH = Path("normalized_data/layout_prompt_library_updated.json")
TOP_K = 3


def main():
    user_prompt = input("Enter your natural language prompt: ")
    library = load_library(LIBRARY_PATH)

    matches = find_top_matches(user_prompt, library, top_k=TOP_K)

    print("\nUSER PROMPT:")
    print(user_prompt)

    print("\nTOP MATCHES:")

    for idx, match in enumerate(matches, start=1):
        print("\n" + "=" * 80)
        print(f"RANK: {idx}")
        print(f"SCORE: {match['score']}")
        print(f"PAGE INDEX: {match['pageIndex']}")

        print("\nMATCHED NATURAL LANGUAGE INTENT:")
        print(match["natural_language_intent"])

        print("\nEXPECTED LAYOUT JSON:")
        print(json.dumps(match["expected_layout_json"], indent=2))


if __name__ == "__main__":
    main()