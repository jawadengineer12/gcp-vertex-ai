import os
import sys
import json
from pathlib import Path
from pydantic import ValidationError

# Import Stage 1 & Stage 2 Retrieval/Rerank Components
from utils.retrieval_utils import load_library, find_top_matches, rerank_matches
# Import Generation Component
from scripts.generate_layout import generate_layout
# Import Stage 3 Schema Validation Layer
from schemas.layout_schema import Page

LIBRARY_PATH = Path("normalized_data/layout_prompt_library_updated.json")
STAGE_1_TOP_K = 10  # Broad lexical + semantic retrieval window
FINAL_TOP_K = 2     # Laser-focused context window sent to Gemini
MAX_RETRIES = 3


def main():
    print("Enter your design brief for layout generation:")
    user_prompt = input("> ")

    if not user_prompt.strip():
        print("User prompt cannot be empty.")
        return

    print(f"User Input Received: '{user_prompt}'")

    # --- [STAGE 1 & 2: TWO-STAGE RETRIEVAL PIPELINE] ---
    print("\n==================================================")
    print("--- [STAGE 1: RUNNING LIGHTWEIGHT RETRIEVAL] ---")
    print("==================================================")
    library = load_library(LIBRARY_PATH)

    # Step 1: Cast a wide net using your custom hybrid search formula
    broad_matches = find_top_matches(user_prompt, library, top_k=STAGE_1_TOP_K)
    print(
        f"Successfully retrieved top {len(broad_matches)} historical candidates via Hybrid Search.")

    print("\n==================================================")
    print("--- [STAGE 2: RUNNING CROSS-ENCODER RERANKER] ---")
    print("==================================================")
    # Step 2: Use deep attention cross-encoder to select structurally accurate templates
    reranked_matches = rerank_matches(user_prompt, broad_matches)

    # Slice the highest quality contexts
    final_context_matches = reranked_matches[:FINAL_TOP_K]
    print(
        f"Distilled down to the top {len(final_context_matches)} highest-precision structural patterns.")

    # Pass the precision matches and initial prompt to the context tracker
    active_prompt = user_prompt
    history_context = final_context_matches

    # --- [STAGES 3 & 4: GENERATION & AGENTIC SELF-CORRECTION LOOP] ---
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

            # Run data contract validations against your strict layout model
            validated_layout = Page(**final_json_data)

            # If it compiles without exceptions, break out immediately
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

    # --- [STAGE 5: PERSISTENCE EXPORT] ---
    output_file = Path("outputs/generated_layout.json")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_json_data, f, indent=2)

    print(f"\n🚀 Validated layout configuration safely saved to: {output_file}")


if __name__ == "__main__":
    main()

    print("\n🎉 [SUCCESS]: Layout generation pipeline completed successfully.")