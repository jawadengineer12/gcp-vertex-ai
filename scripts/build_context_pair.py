# scripts/build_context_pair.py
"""
Parses the raw layout description text file and builds the initial
prompt library JSON with stable IDs.

Run this once to generate normalized_data/layout_prompt_library.json
from the raw text data file.
"""
import json
import re
from pathlib import Path

from config.config import AppConfig
from core.logger import setup_logging, get_logger
from utils.retrieval_utils import build_stable_id

setup_logging()
logger = get_logger(__name__)


def extract_valid_json_block(text: str, start_idx: int) -> tuple[str | None, int]:
    """
    Finds and extracts a perfectly balanced JSON object starting from start_idx.
    """
    brace_count = 0
    in_string = False
    escape_char = False

    for i in range(start_idx, len(text)):
        char = text[i]

        if char == '"' and not escape_char:
            in_string = not in_string

        if in_string:
            if char == "\\":
                escape_char = not escape_char
            else:
                escape_char = False
            continue

        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                return text[start_idx: i + 1], i

    return None, -1


def process_description_dataset() -> None:
    raw_data_path = AppConfig.RAW_TEXT_DATA_PATH
    output_path = AppConfig.PROMPT_LIBRARY_PATH

    logger.info("Build context pair script started.")
    logger.info("Raw text data path: %s", raw_data_path)
    logger.info("Output prompt library path: %s", output_path)

    if not raw_data_path.exists():
        logger.error("Raw description file not found: %s", raw_data_path)
        print(f"Error: Could not find raw file at '{raw_data_path}'")
        return

    with open(raw_data_path, "r", encoding="utf-8") as f:
        file_text = f.read()

    logger.info("Raw file loaded | chars=%d", len(file_text))
    print("Running pipeline...")

    raw_blocks = re.split(r'(?={"pageIndex":\d+)', file_text)
    final_library = []
    logger.info("Split raw text into blocks | count=%d", len(raw_blocks))

    for block_idx, block in enumerate(raw_blocks):
        if not block.strip():
            continue

        json_match = re.search(
            r'({"pageIndex":\d+,"assets":\[.*)',
            block,
            re.DOTALL,
        )

        if not json_match:
            logger.debug("No JSON match in block | block_index=%d", block_idx)
            continue

        json_str, _ = extract_valid_json_block(json_match.group(1), 0)

        if not json_str:
            logger.warning(
                "Could not extract balanced JSON | block_index=%d", block_idx
            )
            continue

        try:
            page_data = json.loads(json_str, strict=False)
            page_index = page_data["pageIndex"]

            text_context = block.replace(json_str, "").strip()
            clean_intent = re.sub(r"[\r\n\t]+", " ", text_context)
            clean_intent = re.sub(
                r"^(Description:\s*|,\s*|Description\s*:\s*)",
                "",
                clean_intent,
                flags=re.IGNORECASE,
            )
            clean_intent = " ".join(clean_intent.split()).strip()

            if not clean_intent or len(clean_intent) < 10:
                clean_intent = (
                    f"Generate the layout grid and component coordinate "
                    f"structure for Page {page_index}."
                )

            entry = {
                "pageIndex": page_index,
                "natural_language_intent": clean_intent,
                "expected_layout_json": page_data,
            }
            # Assign stable ID at build time
            entry["id"] = build_stable_id(entry, len(final_library))

            final_library.append(entry)
            logger.info("Extracted page | pageIndex=%d | id=%s",
                        page_index, entry["id"])
            print(f"✅ Extracted Page Index [{page_index}] — ID: {entry['id']}")

        except (json.JSONDecodeError, KeyError) as error:
            logger.warning(
                "Skipping block | block_index=%d | error=%s", block_idx, str(
                    error)
            )
            continue

    final_library.sort(key=lambda x: x["pageIndex"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as out_f:
        json.dump(final_library, out_f, indent=2)

    logger.info(
        "Prompt library built | path=%s | records=%d", output_path, len(
            final_library)
    )
    print(f"\n✅ Prompt library saved to: '{output_path}'")
    print(f"Total entries: {len(final_library)}")


if __name__ == "__main__":
    process_description_dataset()
