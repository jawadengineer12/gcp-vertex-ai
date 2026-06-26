# main.py
import sys
import json
import logging
from pathlib import Path

from core.logger import setup_logging
from config.config import AppConfig
from services.retrieval_service import RetrievalService
from services.reranker_service import RerankerService
from services.generation_service import GenerationService
from services.validation_service import ValidationService
from services.trace_service import build_trace, write_trace

# Must be first — initializes console + file logging before any other import logs
setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=" * 60)
    logger.info("Layout Generation Pipeline started.")

    print("Enter your design brief for layout generation:")
    user_prompt = input("> ").strip()

    if not user_prompt:
        logger.error("Empty prompt. Exiting.")
        print("User prompt cannot be empty.")
        sys.exit(1)

    logger.info("User prompt received | length=%d", len(user_prompt))

    # ── Initialize services ───────────────────────────────────────────────────
    reranker = RerankerService()
    retrieval = RetrievalService()
    generator = GenerationService()
    validator = ValidationService()

    # ── Stage 1 & 2: Hybrid retrieval + reranking ─────────────────────────────
    print("\n" + "=" * 60)
    print("--- [STAGE 1: HYBRID RETRIEVAL (VECTOR + BM25)] ---")
    retrieval_result = retrieval.execute_pipeline(user_prompt)

    vector_candidates = retrieval_result["vector_candidates"]
    bm25_candidates = retrieval_result["bm25_candidates"]
    merged_candidates = retrieval_result["merged_candidates"]

    print(f"\n  ▸ Vector candidates :  {len(vector_candidates)}")
    for c in vector_candidates:
        print(
            f"    ID={c['id']}  pageIndex={c['pageIndex']}  vector_score={c['vector_score']:.4f}")

    print(f"\n  ▸ BM25 candidates   :  {len(bm25_candidates)}")
    for c in bm25_candidates:
        print(
            f"    ID={c['id']}  pageIndex={c['pageIndex']}  bm25_score={c['bm25_score']:.4f}")

    print(f"\n  ▸ Merged candidates :  {len(merged_candidates)}")
    for c in merged_candidates:
        print(
            f"    ID={c['id']}  pageIndex={c['pageIndex']}  "
            f"final_score={c['final_score']:.4f}  "
            f"(v={c['vector_score']:.4f} bm25={c['bm25_score']:.4f})"
        )

    print("\n" + "=" * 60)
    print("--- [STAGE 2: CROSS-ENCODER RERANKING] ---")
    reranked_candidates = reranker.rerank_candidates(
        user_prompt, merged_candidates)
    selected_context = reranked_candidates[: AppConfig.TOP_K_CONTEXT]

    print(f"\n  ▸ Reranked candidates : {len(reranked_candidates)}")
    for c in reranked_candidates:
        print(
            f"    ID={c['id']}  pageIndex={c['pageIndex']}  "
            f"rerank_score={c['rerank_score']:.4f}"
        )

    print(f"\n  ▸ Selected context   : {len(selected_context)} examples")
    for c in selected_context:
        print(f"    ID={c['id']}  pageIndex={c['pageIndex']}")

    logger.info(
        "Retrieval complete | vector=%d | bm25=%d | merged=%d | reranked=%d | context=%d",
        len(vector_candidates),
        len(bm25_candidates),
        len(merged_candidates),
        len(reranked_candidates),
        len(selected_context),
    )

    # ── Stage 3 & 4: Generation + agentic self-correction loop ───────────────
    active_prompt = user_prompt
    attempt = 0
    final_json_data = None
    gemini_raw_response = ""
    validation_success = False
    validation_errors: list[str] = []

    while attempt < AppConfig.MAX_RETRIES:
        attempt += 1

        print(f"\n{'=' * 60}")
        print(
            f"--- [RUNNING INFERENCE — ATTEMPT {attempt}/{AppConfig.MAX_RETRIES}] ---")
        print("=" * 60)

        raw_ai_response = generator.generate_layout_json(
            active_prompt, selected_context)
        gemini_raw_response = raw_ai_response or ""

        if not raw_ai_response:
            logger.error("Generation failed on attempt %d.", attempt)
            print(f"[ERROR]: Generation failed on attempt {attempt}.")
            continue

        print("\n--- [RAW GEMINI RESPONSE] ---")
        print(raw_ai_response)
        print("-" * 48)

        print("\n--- [RUNNING PYDANTIC VALIDATION GATE] ---")
        try:
            final_json_data = validator.validate_payload(raw_ai_response)
            validation_success = True
            validation_errors = []
            logger.info("Validation passed on attempt %d.", attempt)
            print(f"\n🎉 [SUCCESS]: Layout validated on attempt {attempt}!")
            break

        except Exception as error:
            error_str = str(error)
            validation_errors.append(error_str)
            logger.warning(
                "Validation failed on attempt %d: %s", attempt, error_str
            )
            print(f"\n❌ [VALIDATION FAILED on attempt {attempt}]:")
            print(error_str)

            if attempt == AppConfig.MAX_RETRIES:
                logger.error(
                    "Max retries (%d) exhausted. Terminating.", AppConfig.MAX_RETRIES
                )
                print(
                    "\n[CRITICAL]: Maximum retry threshold exhausted. Terminating.")
                sys.exit(1)

            print("\n🔄 [SELF-CORRECTION]: Sending error trace back to Gemini...")
            feedback_brief = (
                f"Your previous JSON response failed our automated schema validation checks.\n"
                f"STRICT ERROR TRACE FROM CLIENT RUNTIME:\n{error_str}\n\n"
                f"Please fix the schema naming issues or coordinate values listed above, "
                f"re-evaluate your rules mapping, and provide the entire corrected JSON structure."
            )
            active_prompt = f"{user_prompt}\n\n[CRITICAL FIX REQUIRED]:\n{feedback_brief}"

    # ── Stage 5: Save output ──────────────────────────────────────────────────
    output_file = AppConfig.OUTPUT_FILE
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_json_data, f, indent=2)

    logger.info("Output saved: %s", output_file)
    print(f"\n🚀 Validated layout saved to: {output_file}")

    # ── Stage 6: Write run trace ──────────────────────────────────────────────
    trace = build_trace(
        user_prompt=user_prompt,
        vector_candidates=vector_candidates,
        bm25_candidates=bm25_candidates,
        merged_candidates=merged_candidates,
        reranked_candidates=reranked_candidates,
        selected_context=selected_context,
        gemini_raw_response=gemini_raw_response,
        parsed_json=final_json_data,
        validation_success=validation_success,
        validation_errors=validation_errors,
        output_file=str(output_file),
    )
    trace_path = write_trace(trace)
    if trace_path:
        print(f"📋 Run trace saved to: {trace_path}")

    logger.info("Pipeline completed successfully.")
    print("\n🎉 [SUCCESS]: Layout generation pipeline completed.")


if __name__ == "__main__":
    main()
