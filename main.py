import sys
import json

from json import JSONDecodeError
from pydantic import ValidationError

from core.config import (
    UPDATED_LIBRARY_PATH,
    STAGE_1_TOP_K,
    FINAL_TOP_K,
    MAX_RETRIES,
    GENERATED_LAYOUT_PATH,
)

from core.run_recorder import RunRecorder
from core.logger import setup_logging, get_logger

from services.retrieval_service import load_library, retrieve_hybrid_matches
from services.reranker_service import rerank_matches
from services.generation_service import generate_layout
from services.validation_service import parse_and_validate_layout


# -----------------------------
# INIT LOGGING
# -----------------------------
setup_logging()
LOGGER = get_logger(__name__)


# -----------------------------
# PIPELINE
# -----------------------------
def run_pipeline(user_prompt: str):

    LOGGER.info("PIPELINE STARTED")
    LOGGER.info("User prompt received | length=%s", len(user_prompt))

    print("\n==================================================")
    print("🚀 STAGE 1: HYBRID RETRIEVAL")
    print("==================================================")

    recorder = RunRecorder()
    recorder.set_prompt(user_prompt)
    
    # 1. Load library
    library = load_library(UPDATED_LIBRARY_PATH)
    LOGGER.info("Library loaded | size=%s", len(library))

    # 2. Hybrid retrieval
    candidates = retrieve_hybrid_matches(
        user_prompt=user_prompt,
        library=library,
        top_k=STAGE_1_TOP_K,
    )

    recorder.set_retrieval(candidates)
    LOGGER.info("Hybrid retrieval done | candidates=%s", len(candidates))

    # 3. Reranking
    print("\n==================================================")
    print("🎯 STAGE 2: RERANKING")
    print("==================================================")

    reranked = rerank_matches(user_prompt, candidates)
    context = reranked[:FINAL_TOP_K]
    
    recorder.set_reranked(reranked)
    recorder.set_context(context)
    LOGGER.info("Reranking done | final_context=%s", len(context))

    # -----------------------------
    # GENERATION + VALIDATION LOOP
    # -----------------------------
    final_json = None

    for attempt in range(1, MAX_RETRIES + 1):

        print("\n==================================================")
        print(f"🤖 STAGE 3: GENERATION (Attempt {attempt})")
        print("==================================================")

        LOGGER.info("Generation attempt started | attempt=%s", attempt)

        raw_response = generate_layout(user_prompt, context)

        if not raw_response:
            LOGGER.error("Empty response from model")
            continue
        
        recorder.set_generation(raw_response)
        LOGGER.info("Raw response received | chars=%s", len(raw_response))

        print("\n--- RAW RESPONSE ---\n")
        print(raw_response)

        print("\n==================================================")
        print("🔍 STAGE 4: VALIDATION")
        print("==================================================")

        try:
            final_json, _ = parse_and_validate_layout(raw_response)

            recorder.set_validation_status("success")
            LOGGER.info("VALIDATION SUCCESS | attempt=%s", attempt)
            print("\n🎉 SUCCESS: Valid layout generated!")

            break

        except (JSONDecodeError, ValidationError) as e:
            recorder.set_validation_status("failed")
            LOGGER.error(
                "Validation failed | attempt=%s | error=%s", attempt, str(e))

            if attempt == MAX_RETRIES:
                LOGGER.critical("MAX RETRIES REACHED — FAILING PIPELINE")
                print("\n❌ Pipeline failed after max retries")
                sys.exit(1)

            print("\n⚠️ Fixing and retrying...\n")

            user_prompt = (
                user_prompt
                + "\n\n[FIX REQUIRED]\n"
                + str(e)
            )

    # -----------------------------
    # SAVE OUTPUT
    # -----------------------------
    if final_json:
        GENERATED_LAYOUT_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(GENERATED_LAYOUT_PATH, "w", encoding="utf-8") as f:
            json.dump(final_json, f, indent=2)

        LOGGER.info("OUTPUT SAVED | path=%s", GENERATED_LAYOUT_PATH)

        print("\n💾 Saved output to:", GENERATED_LAYOUT_PATH)
        
        run_file = recorder.save()
        LOGGER.info("Run trace saved | file=%s", run_file)
        print(f"\n📦 Full run saved at: {run_file}")

    LOGGER.info("PIPELINE FINISHED")

    return final_json


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":

    print("Enter your design prompt:")
    prompt = input("> ")

    run_pipeline(prompt)
