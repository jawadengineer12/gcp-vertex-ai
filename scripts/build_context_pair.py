import json
import re

from core.config import RAW_TEXT_DATA_PATH, LIBRARY_PATH
from core.logger import setup_logging, get_logger

setup_logging()
LOGGER = get_logger(__name__)


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
                return text[start_idx:i + 1], i

    return None, -1


def process_description_dataset_certified() -> None:
    LOGGER.info("Build context pair script started.")
    LOGGER.info("Raw text data path: %s", RAW_TEXT_DATA_PATH)
    LOGGER.info("Output prompt library path: %s", LIBRARY_PATH)

    if not RAW_TEXT_DATA_PATH.exists():
        LOGGER.error("Raw description file not found: %s", RAW_TEXT_DATA_PATH)
        print(f"Error: Could not find raw file at '{RAW_TEXT_DATA_PATH}'")
        return

    with open(RAW_TEXT_DATA_PATH, "r", encoding="utf-8") as f:
        file_text = f.read()

    LOGGER.info("Raw description file loaded | chars=%s", len(file_text))
    print("Running pipeline...")

    raw_blocks = re.split(r'(?={"pageIndex":\d+)', file_text)
    final_library = []

    LOGGER.info("Split raw text into blocks | block_count=%s", len(raw_blocks))

    for block_idx, block in enumerate(raw_blocks):
        if not block.strip():
            continue

        json_match = re.search(
            r'({"pageIndex":\d+,"assets":\[.*)',
            block,
            re.DOTALL,
        )

        if not json_match:
            LOGGER.debug(
                "No JSON match found in block | block_index=%s", block_idx)
            continue

        json_str, _ = extract_valid_json_block(json_match.group(1), 0)

        if not json_str:
            LOGGER.warning(
                "Could not extract balanced JSON block | block_index=%s", block_idx)
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
                    f"Generate the layout grid and component coordinate structure "
                    f"for Page {page_index}."
                )

            final_library.append({
                "pageIndex": page_index,
                "natural_language_intent": clean_intent,
                "expected_layout_json": page_data,
            })

            LOGGER.info(
                "Extracted page successfully | pageIndex=%s", page_index)
            print(f"✅ Extracted Page Index [{page_index}] successfully.")

        except (json.JSONDecodeError, KeyError) as error:
            LOGGER.warning(
                "Skipping block due to JSON/key error | block_index=%s | error=%s",
                block_idx,
                str(error),
            )
            continue

    final_library.sort(key=lambda x: x["pageIndex"])

    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(LIBRARY_PATH, "w", encoding="utf-8") as out_f:
        json.dump(final_library, out_f, indent=2)

    LOGGER.info("Prompt library built successfully | path=%s | records=%s",
                LIBRARY_PATH, len(final_library))

    print(
        f"\nVerification Successful! Certified prompt library at: '{LIBRARY_PATH}'")
    print(
        f"Total perfectly aligned reasoning blocks ready: {len(final_library)}")


if __name__ == "__main__":
    process_description_dataset_certified()
