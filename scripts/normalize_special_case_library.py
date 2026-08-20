"""Sanitize whole-project special cases without splitting or dropping empty pages."""

import argparse
import json
from copy import deepcopy
from pathlib import Path

from core.config import AppConfig
from services.font_service import load_allowed_fonts
from services.sanitization_service import sanitize_retrieved_examples


def normalize_cases(cases: list[dict], allowed_fonts: list[str]) -> list[dict]:
    normalized = deepcopy(cases)
    candidates = [
        {"expected_layout_json": case.get("example")} for case in normalized
    ]
    sanitized = sanitize_retrieved_examples(candidates, allowed_fonts)
    for case, candidate in zip(normalized, sanitized, strict=True):
        case["example"] = candidate["expected_layout_json"]
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.source.read_text(encoding="utf-8"))
    normalized = normalize_cases(
        cases, load_allowed_fonts(AppConfig.FONT_LIST_PATH)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
