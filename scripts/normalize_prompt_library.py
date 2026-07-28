"""Create a sanitized prompt library suitable for generation context.

This is a local preparation step. It does not rebuild or update the cloud index.
"""

import argparse
import json
from pathlib import Path

from core.config import AppConfig
from services.font_service import load_allowed_fonts
from services.sanitization_service import sanitize_retrieved_examples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=AppConfig.PROMPT_LIBRARY_PATH)
    parser.add_argument(
        "--output", type=Path, default=Path("normalized_data/layout_prompt_library_sanitized.json")
    )
    args = parser.parse_args()

    with args.source.open("r", encoding="utf-8") as handle:
        candidates = json.load(handle)
    fonts = load_allowed_fonts(AppConfig.FONT_LIST_PATH)
    sanitized = sanitize_retrieved_examples(candidates, fonts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(sanitized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(sanitized)} sanitized examples to {args.output}")


if __name__ == "__main__":
    main()
