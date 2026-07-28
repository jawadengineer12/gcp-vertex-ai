"""Interactive reliable LayoutProject generation pipeline."""

import json
import logging
import sys

from core.config import AppConfig
from core.logger import setup_logging
from services.font_service import load_allowed_fonts
from services.generation_service import GenerationService
from services.information_agent import InformationAgent
from services.output_service import OutputService
from services.requirement_agent import RequirementAgent
from services.retrieval_service import RetrievalService
from services.reranker_service import RerankerService
from services.sanitization_service import sanitize_retrieved_examples
from services.template_service import TemplateRegistry
from services.trace_service import build_trace, write_trace
from services.validation_service import ValidationService

setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Layout Generation Pipeline started")

    template = TemplateRegistry(AppConfig.TEMPLATE_DIR).choose()
    if template:
        print(f"\nLoading template: {template['name']}")
        print(json.dumps(template.get("defaultSettings", {}), indent=2))

    print("\nDescribe your layout:")
    user_prompt = input("> ").strip()
    if not user_prompt:
        print("User prompt cannot be empty.")
        raise SystemExit(1)

    allowed_fonts = load_allowed_fonts(AppConfig.FONT_LIST_PATH)
    requirement_agent = RequirementAgent()
    required_fields = requirement_agent.resolve(user_prompt, template)
    known_values = requirement_agent.extract_known_values(user_prompt, required_fields)
    collected_fields = InformationAgent().collect(required_fields, known_values)

    enriched_prompt = user_prompt
    if collected_fields:
        enriched_prompt += "\n\nConfirmed user information:\n" + json.dumps(
            collected_fields, ensure_ascii=False
        )

    print("\n--- Retrieving structural layout references ---")
    retrieval = RetrievalService()
    reranker = RerankerService()
    retrieval_result = retrieval.execute_pipeline(enriched_prompt)
    reranked_candidates = reranker.rerank_candidates(
        enriched_prompt, retrieval_result["merged_candidates"]
    )
    selected_context = sanitize_retrieved_examples(
        reranked_candidates[: AppConfig.TOP_K_CONTEXT], allowed_fonts
    )

    generator = GenerationService()
    validator = ValidationService(
        allowed_fonts,
        safe_margin=AppConfig.SAFE_MARGIN,
        image_bleed=AppConfig.IMAGE_BLEED,
        ad_tolerance=AppConfig.AD_BOUNDARY_TOLERANCE,
    )
    final_json_data: dict | None = None
    gemini_raw_response = ""
    validation_errors: list[str] = []
    active_prompt = user_prompt

    for attempt in range(1, AppConfig.MAX_RETRIES + 1):
        print(f"\n--- Generation attempt {attempt}/{AppConfig.MAX_RETRIES} ---")
        response = generator.generate_layout_json(
            active_prompt,
            selected_context,
            collected_fields,
            allowed_fonts,
            template,
        )
        gemini_raw_response = response or ""
        if not response:
            validation_errors.append(f"attempt {attempt}: empty generation response")
            continue
        try:
            final_json_data = validator.validate_payload(response)
            break
        except Exception as error:
            error_text = str(error)
            validation_errors.append(f"attempt {attempt}: {error_text}")
            logger.warning("Validation failed on attempt %d: %s", attempt, error_text)
            active_prompt = (
                f"{user_prompt}\n\nYour previous output failed validation. Correct every "
                f"reported issue and return the complete LayoutProject again:\n{error_text}"
            )

    if final_json_data is None:
        print("Generation failed the validation gate after all retries.")
        for error in validation_errors:
            print(f"- {error}")
        raise SystemExit(1)

    destinations = OutputService(
        output_file=AppConfig.OUTPUT_FILE,
        local_output=AppConfig.LOCAL_OUTPUT,
        gcs_bucket=AppConfig.GCS_BUCKET,
        gcs_object_name=AppConfig.GCS_OBJECT_NAME,
    ).save_json(final_json_data)
    for kind, destination in destinations.items():
        print(f"Validated JSON saved ({kind}): {destination}")

    trace = build_trace(
        user_prompt=user_prompt,
        template=template,
        collected_fields=collected_fields,
        vector_candidates=retrieval_result["vector_candidates"],
        bm25_candidates=retrieval_result["bm25_candidates"],
        merged_candidates=retrieval_result["merged_candidates"],
        reranked_candidates=reranked_candidates,
        selected_context=selected_context,
        gemini_raw_response=gemini_raw_response,
        parsed_json=final_json_data,
        validation_success=True,
        validation_errors=validation_errors,
        destinations=destinations,
    )
    trace_path = write_trace(trace)
    if trace_path:
        print(f"Run trace saved: {trace_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
