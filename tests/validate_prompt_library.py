"""Regression check for the 32 real converter examples."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import AppConfig
from services.font_service import load_allowed_fonts
from services.sanitization_service import sanitize_retrieved_examples


def main() -> None:
    library = json.loads(AppConfig.PROMPT_LIBRARY_PATH.read_text(encoding="utf-8"))
    fonts = load_allowed_fonts(AppConfig.FONT_LIST_PATH)
    candidates = sanitize_retrieved_examples(library, fonts)
    article_count = 0

    for candidate in candidates:
        layout = candidate["expected_layout_json"]
        pages = layout.get("pages", [layout])
        for page in pages:
            for asset in page.get("assets", []):
                content = asset.get("content", {})
                if asset.get("assetType") == "Article":
                    article_count += 1
                    for field in ("columns", "gutterSize", "margins", "textStyle"):
                        assert field in asset, f"{candidate.get('id')}: missing {field}"
                        assert field not in content, f"{candidate.get('id')}: nested {field}"
                    assert asset["textStyle"]["fontFamily"] in fonts
                elif "imageUrl" in content:
                    image_url = content["imageUrl"]
                    assert image_url.startswith("https://") or (
                        image_url.startswith("[") and image_url.endswith("_url]")
                    ), f"{candidate.get('id')}: unsafe imageUrl"

    assert article_count, "Prompt library contains no Article assets"
    print(f"Validated {len(candidates)} examples and {article_count} Article assets.")


if __name__ == "__main__":
    main()
