import json
import sys
from pathlib import Path


LIBRARY_PATH = Path("normalized_data/layout_prompt_library.json")


def load_library(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def score_prompt(user_prompt: str, example_text: str) -> int:
    user_words = set(user_prompt.lower().split())
    example_words = set(example_text.lower().split())
    return len(user_words.intersection(example_words))


def find_best_match(user_prompt: str, library: list):
    best_item = None
    best_score = -1

    for item in library:
        intent = item.get("natural_language_intent", "")
        score = score_prompt(user_prompt, intent)

        if score > best_score:
            best_score = score
            best_item = item

    return best_item, best_score


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_retrieval.py \"your layout prompt here\"")
        return

    user_prompt = " ".join(sys.argv[1:])
    library = load_library(LIBRARY_PATH)

    match, score = find_best_match(user_prompt, library)

    print("\nUSER PROMPT:")
    print(user_prompt)

    print("\nBEST MATCH SCORE:")
    print(score)

    print("\nMATCHED PAGE INDEX:")
    print(match.get("pageIndex"))

    print("\nMATCHED NATURAL LANGUAGE INTENT:")
    print(match.get("natural_language_intent"))

    print("\nEXPECTED LAYOUT JSON:")
    print(json.dumps(match.get("expected_layout_json"), indent=2))


if __name__ == "__main__":
    main()