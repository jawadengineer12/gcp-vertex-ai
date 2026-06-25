import json

import pandas as pd

from core.config import EXCEL_FILE_PATH, LIBRARY_PATH, UPDATED_LIBRARY_PATH
from core.logger import setup_logging, get_logger

setup_logging()
LOGGER = get_logger(__name__)


def main() -> None:
    LOGGER.info("Append Excel script started.")
    LOGGER.info("Base library path: %s", LIBRARY_PATH)
    LOGGER.info("Excel file path: %s", EXCEL_FILE_PATH)
    LOGGER.info("Output library path: %s", UPDATED_LIBRARY_PATH)

    if not LIBRARY_PATH.exists():
        LOGGER.error("Base prompt library not found: %s", LIBRARY_PATH)
        raise FileNotFoundError(
            f"Base prompt library not found: {LIBRARY_PATH}")

    if not EXCEL_FILE_PATH.exists():
        LOGGER.error("Excel training file not found: %s", EXCEL_FILE_PATH)
        raise FileNotFoundError(
            f"Excel training file not found: {EXCEL_FILE_PATH}")

    with open(LIBRARY_PATH, "r", encoding="utf-8") as f:
        library = json.load(f)

    LOGGER.info("Loaded base prompt library | records=%s", len(library))

    df = pd.read_excel(EXCEL_FILE_PATH)
    LOGGER.info("Loaded Excel training data | rows=%s", len(df))

    appended_count = 0
    skipped_invalid_json = 0
    skipped_empty_assets = 0

    for idx, row in df.iterrows():
        expected_json_str = row.get("Expected JSON Object (Output)")

        try:
            expected_json = json.loads(expected_json_str)
        except Exception:
            skipped_invalid_json += 1
            LOGGER.warning(
                "Skipping row due to invalid JSON | row_index=%s", idx)
            continue

        if expected_json.get("assets") == []:
            skipped_empty_assets += 1
            LOGGER.info("Skipping row with empty assets | row_index=%s", idx)
            continue

        new_entry = {
            "pageIndex": int(row["Page Number"]),
            "natural_language_intent": row["Generated Prompt (Input)"],
            "expected_layout_json": expected_json,
        }

        library.append(new_entry)
        appended_count += 1

    UPDATED_LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(UPDATED_LIBRARY_PATH, "w", encoding="utf-8") as f:
        json.dump(library, f, indent=2)

    LOGGER.info("Updated prompt library saved: %s", UPDATED_LIBRARY_PATH)
    LOGGER.info("Append summary | appended=%s | invalid_json=%s | empty_assets=%s | final_records=%s",
                appended_count, skipped_invalid_json, skipped_empty_assets, len(library))

    print(f"Updated library saved to {UPDATED_LIBRARY_PATH}")
    print(f"Appended rows: {appended_count}")
    print(f"Skipped invalid JSON rows: {skipped_invalid_json}")
    print(f"Skipped empty asset rows: {skipped_empty_assets}")
    print(f"Final library size: {len(library)}")


if __name__ == "__main__":
    main()
