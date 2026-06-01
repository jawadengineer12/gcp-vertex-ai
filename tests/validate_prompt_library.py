import json
from pathlib import Path
from pydantic import ValidationError

# Import your core structural models directly from your schema file
from schemas.layout_schema import Page


def execute_prompt_library_validation():
    library_path = Path("normalized_data/layout_prompt_library.json")

    if not library_path.exists():
        print(
            f"Error: Automated test failed. Could not locate '{library_path}'")
        return

    with open(library_path, "r", encoding="utf-8") as f:
        prompt_library = json.load(f)

    print(
        f"Loaded prompt library containing {len(prompt_library)} learning items.")
    print("Starting Pydantic schema validation tests...\n")

    passed_records = 0
    failed_records = 0

    for entry in prompt_library:
        page_index = entry.get("pageIndex")
        raw_layout_json = entry.get("expected_layout_json")

        try:
            # Force structural validation against your precise schema rules
            validated_page_model = Page(**raw_layout_json)

            print(
                f"[Page {page_index:02d}]: Structural data matches Pydantic schema constraints.")
            passed_records += 1

        except ValidationError as e:
            print(
                f"[Page {page_index:02d}]: Schema non-compliance detected!")
            print(f"   Detailed structural error map:\n{e}\n")
            failed_records += 1

    print("\nValidation Test Suite Summary Execution:")
    print(f"   - Perfectly compliant paired records: {passed_records}")
    print(f"   - Non-compliant flagged records: {failed_records}")

    if failed_records == 0:
        print(
            "\nSuccess! All data components match your production structures perfectly.")
        print("   Milestone One Local Pipeline is officially complete and airtight!")
    else:
        print("\nWarning: Minor data format cleanup required within the pipeline before handoff.")


if __name__ == "__main__":
    execute_prompt_library_validation()
