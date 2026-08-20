"""Interactive CLI adapter for the shared layout pipeline."""

import argparse
import json
import logging
import sys

from core.config import AppConfig
from core.logger import setup_logging
from services.information_agent import InformationAgent
from services.output_service import OutputService
from services.requirement_agent import RequirementAgent
from services.template_service import TemplateRegistry
from services.trace_service import build_trace, write_trace

logger = logging.getLogger(__name__)


def _publisher_settings(enabled: bool) -> tuple[str, str]:
    if not enabled:
        return "", ""
    if not AppConfig.PUBLISHER_API_URL or not AppConfig.PUBLISHER_API_KEY:
        raise ValueError(
            "--publish requires PUBLISHER_API_URL and PUBLISHER_API_KEY"
        )
    return AppConfig.PUBLISHER_API_URL, AppConfig.PUBLISHER_API_KEY


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--publish",
        action="store_true",
        help="submit validated JSON to the configured publisher",
    )
    args = parser.parse_args(argv)
    try:
        publisher_url, publisher_api_key = _publisher_settings(args.publish)
    except ValueError as error:
        parser.error(str(error))
    setup_logging()
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

    requirement_agent = RequirementAgent()
    required_fields = requirement_agent.resolve(user_prompt, template)
    known_values = requirement_agent.extract_known_values(user_prompt, required_fields)
    collected_fields = InformationAgent().collect(required_fields, known_values)

    from services.pipeline_service import PipelineGenerationError, get_pipeline_service

    try:
        result = get_pipeline_service().generate(
            user_prompt, collected_fields, template
        )
    except PipelineGenerationError as error:
        print("Generation failed the validation gate after all retries.")
        for detail in error.errors:
            print(f"- {detail}")
        raise SystemExit(1) from error

    output = OutputService(
        output_file=AppConfig.OUTPUT_FILE,
        local_output=AppConfig.LOCAL_OUTPUT,
        gcs_bucket=AppConfig.GCS_BUCKET,
        gcs_object_name=AppConfig.GCS_OBJECT_NAME,
        publisher_url=publisher_url,
        publisher_api_key=publisher_api_key,
        publisher_created_by=AppConfig.PUBLISHER_CREATED_BY,
        publisher_project=AppConfig.PUBLISHER_PROJECT,
    )
    destinations = output.save_json(result.layout)
    for kind, destination in destinations.items():
        print(f"Validated JSON saved ({kind}): {destination}")
    try:
        publisher_response = output.queue_job(result.layout)
    except RuntimeError as error:
        print(f"Publisher submission failed: {error}")
        raise SystemExit(1) from error
    if publisher_response:
        status, body = publisher_response
        destinations["publisher"] = AppConfig.PUBLISHER_API_URL
        print(f"Publisher queue accepted ({status}): {body or 'empty response'}")

    trace = build_trace(
        user_prompt=user_prompt,
        template=template,
        collected_fields=collected_fields,
        vector_candidates=result.retrieval_result["vector_candidates"],
        bm25_candidates=result.retrieval_result["bm25_candidates"],
        merged_candidates=result.retrieval_result["merged_candidates"],
        reranked_candidates=result.reranked_candidates,
        selected_context=result.selected_context,
        gemini_raw_response=result.raw_response,
        parsed_json=result.layout,
        validation_success=True,
        validation_errors=result.validation_errors,
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
