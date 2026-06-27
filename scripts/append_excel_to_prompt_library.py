# scripts/append_excel_to_prompt_library.py
"""
Appends new training examples from an Excel file to the existing prompt library.
Assigns stable IDs to all new entries.
Run prepare_vertex_vector_data.py after this to regenerate embeddings.
"""
import json
import pandas as pd
from config.config import AppConfig
from core.logger import setup_logging, get_logger
from utils.retrieval_utils import build_stable_id

setup_logging()
logger = get_logger(__name__)


def main() -> None:
    library_path = AppConfig.PROMPT_LIBRARY_PATH
    excel_path = AppConfig.EXCEL_FILE_PATH

    logger.info("Append Excel script started.")
    logger.info("Library path: %s", library_path)
    logger.info("Excel path: %s", excel_path)

    if not library_path.exists():
        raise FileNotFoundError(f"Prompt library not found: {library_path}")

    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    with open(library_path, "r", encoding="utf-8") as f:
        library: list[dict] = json.load(f)

    logger.info("Loaded existing library | records=%d", len(library))

    # Ensure all existing entries have stable IDs
    updated_existing = False
    for idx, item in enumerate(library):
        if "id" not in item or not item["id"]:
            item["id"] = build_stable_id(item, idx)
            updated_existing = True

    df = pd.read_excel(excel_path)
    logger.info("Loaded Excel | rows=%d", len(df))

    appended = 0
    skipped_invalid = 0
    skipped_empty = 0
    start_index = len(library)

    for row_idx, row in df.iterrows():
        expected_json_str = row.get("Expected JSON Object (Output)")

        try:
            expected_json = json.loads(expected_json_str)
        except Exception:
            skipped_invalid += 1
            logger.warning("Skipping row — invalid JSON | row=%s", row_idx)
            continue

        if expected_json.get("assets") == []:
            skipped_empty += 1
            logger.info("Skipping row — empty assets | row=%s", row_idx)
            continue

        entry: dict = {
            "pageIndex": int(row["Page Number"]),
            "natural_language_intent": row["Generated Prompt (Input)"],
            "expected_layout_json": expected_json,
        }
        entry["id"] = build_stable_id(entry, start_index + appended)

        library.append(entry)
        appended += 1

    library_path.parent.mkdir(parents=True, exist_ok=True)

    with open(library_path, "w", encoding="utf-8") as f:
        json.dump(library, f, indent=2)

    logger.info(
        "Append complete | appended=%d | invalid=%d | empty=%d | total=%d",
        appended, skipped_invalid, skipped_empty, len(library),
    )
    print(f"✅ Library updated: {library_path}")
    print(
        f"   Appended: {appended} | Skipped invalid: {skipped_invalid} | Skipped empty: {skipped_empty}")
    print(f"   Total records: {len(library)}")
    print("\nNext: run scripts/prepare_vertex_vector_data.py to regenerate embeddings.")


if __name__ == "__main__":
    main()
