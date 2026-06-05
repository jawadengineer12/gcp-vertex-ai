import os
import sys
import json
from pathlib import Path
from pydantic import ValidationError


# Import Stage 1 Retrieval Components
from utils.retrieval_utils import load_library, find_top_matches
# Import Stage 2 Generation Component
from scripts.generate_layout import generate_layout
# Import Stage 3 Schema Validation Layer
from schemas.layout_schema import Page

LIBRARY_PATH = Path("normalized_data/layout_prompt_library.json")
TOP_K = 2
MAX_RETRIES = 3


def main():
    print("Enter your design brief for layout generation:")
    user_prompt = input("> ")

    if not user_prompt.strip():
        print("User prompt cannot be empty.")
        return

    print(f"User Input Received: '{user_prompt}'")

    # --- [STAGE 1: RETRIEVING REFERENCE CONTEXT] ---
    print("\n==================================================")
    print("--- [STAGE 1: RUNNING LIGHTWEIGHT RETRIEVAL] ---")
    print("==================================================")
    library = load_library(LIBRARY_PATH)
    matches = find_top_matches(user_prompt, library, top_k=TOP_K)
    print(
        f"Successfully retrieved top {len(matches)} historical reference cases.")

    # We will pass the matches and the initial user intent prompt to our tracking context
    active_prompt = user_prompt
    history_context = matches

    # --- [STAGES 2 & 3: GENERATION & SELF-CORRECTION LOOP] ---
    attempt = 0
    validated_layout = None
    final_json_data = None

    while attempt < MAX_RETRIES:
        attempt += 1
        print(f"\n==================================================")
        print(f"--- [RUNNING INFERENCE - ATTEMPT {attempt}/{MAX_RETRIES}] ---")
        print(f"==================================================")

        raw_ai_response = generate_layout(active_prompt, history_context)

        if not raw_ai_response:
            print(
                f"[ERROR]: Live text generation failed on attempt {attempt}.")
            continue

        print(f"\n--- [RAW RESPONSE RECEIVED] ---")
        print(raw_ai_response)
        print("------------------------------------------------")

        print("\n--- [RUNNING PYDANTIC VALIDATION GATE] ---")
        try:
            # Convert raw text response text cleanly into a dictionary object
            final_json_data = json.loads(raw_ai_response.strip())

            # Run data contract validations
            validated_layout = Page(**final_json_data)

            # If it compiles, break out of the retry cycle immediately!
            print(
                f"\n🎉 [SUCCESS]: Layout validated perfectly on attempt {attempt}!")
            break

        except (json.JSONDecodeError, ValidationError) as error:
            print(f"\n❌ [VALIDATION FAILED ON ATTEMPT {attempt}]:")
            print(str(error))

            if attempt == MAX_RETRIES:
                print(
                    "\n[CRITICAL]: Maximum retry threshold exhausted without repair. Terminating.")
                sys.exit(1)

            print(
                "\n🔄 [FEEDBACK ENGINES ENGAGED]: Compiling error trace back to Gemini...")

            # Transform the strict error text into structural correction metadata
            feedback_brief = (
                f"Your previous JSON response failed our automated schema validation checks.\n"
                f"STRICT ERROR TRACE FROM CLIENT RUNTIME:\n{str(error)}\n\n"
                f"Please fix the schema naming issues or coordinate values listed above, "
                f"re-evaluate your rules mapping, and provide the entire corrected JSON structure."
            )

            # Mutate active instruction string to inject loop context
            active_prompt = f"{user_prompt}\n\n[CRITICAL FIX REQUIRED]:\n{feedback_brief}"

    # --- [STAGE 4: PERSISTENCE EXPORT] ---
    output_file = Path("outputs/generated_layout.json")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_json_data, f, indent=2)

    print(f"\n🚀 Validated layout configuration safely saved to: {output_file}")


if __name__ == "__main__":
    main()
