"""Reusable non-interactive layout generation pipeline."""

import json
import logging
from dataclasses import dataclass
from functools import cache
from time import perf_counter

from core.config import AppConfig
from services.font_service import load_allowed_fonts
from services.generation_service import GenerationService
from services.layout_plan_service import LayoutPlanService
from services.reranker_service import RerankerService
from services.retrieval_service import RetrievalService
from services.sanitization_service import sanitize_retrieved_examples
from services.special_case_service import SpecialCaseService
from services.validation_service import ValidationService

logger = logging.getLogger(__name__)


def _milliseconds(start: float) -> int:
    return round((perf_counter() - start) * 1000)


def _log(request_id: str | None, stage: str, duration_ms: int, **values: object) -> None:
    if request_id:
        logger.info(
            json.dumps(
                {"request_id": request_id, "stage": stage, "duration_ms": duration_ms, **values},
                separators=(",", ":"),
            )
        )


@dataclass
class PipelineResult:
    layout: dict
    timing_ms: dict[str, int]
    retries: int
    retrieval_result: dict
    reranked_candidates: list[dict]
    selected_context: list[dict]
    raw_response: str
    validation_errors: list[str]


class PipelineGenerationError(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("Generation failed validation after all retries")
        self.errors = errors


class LayoutPipeline:
    def generate(
        self,
        user_prompt: str,
        collected_fields: dict[str, str],
        template: dict | None = None,
        request_id: str | None = None,
    ) -> PipelineResult:
        total_started = perf_counter()
        layout_plan = LayoutPlanService().plan(user_prompt)
        allowed_fonts = list(get_allowed_fonts())
        enriched_prompt = user_prompt
        if collected_fields:
            enriched_prompt += "\n\nConfirmed user information:\n" + json.dumps(
                collected_fields, ensure_ascii=False
            )

        started = perf_counter()
        retrieval_result = get_retrieval_service().execute_pipeline(enriched_prompt)
        retrieval_ms = _milliseconds(started)
        _log(request_id, "retrieval", retrieval_ms, retries=0, result="completed")

        started = perf_counter()
        reranked_candidates = get_reranker_service().rerank_candidates(
            enriched_prompt, retrieval_result["merged_candidates"]
        )
        selected_context = sanitize_retrieved_examples(
            reranked_candidates[: AppConfig.TOP_K_CONTEXT], allowed_fonts
        )
        selected_context.extend(get_special_case_service().context_for(layout_plan))
        reranking_ms = _milliseconds(started)
        _log(request_id, "reranking", reranking_ms, retries=0, result="completed")

        generator = get_generation_service()
        validator = get_validation_service()
        final_layout: dict | None = None
        raw_response = ""
        validation_errors: list[str] = []
        active_prompt = user_prompt
        generation_ms = 0
        validation_ms = 0
        attempts = 0

        for attempts in range(1, AppConfig.MAX_RETRIES + 1):
            started = perf_counter()
            response = generator.generate_layout_json(
                active_prompt,
                selected_context,
                collected_fields,
                allowed_fonts,
                template,
                layout_plan,
            )
            elapsed = _milliseconds(started)
            generation_ms += elapsed
            raw_response = response or ""
            _log(
                request_id,
                "generation",
                elapsed,
                retries=attempts - 1,
                result="completed" if response else "empty_response",
            )
            if not response:
                validation_errors.append(f"attempt {attempts}: empty generation response")
                continue

            started = perf_counter()
            try:
                final_layout = validator.validate_payload(response, layout_plan)
            except Exception as error:
                elapsed = _milliseconds(started)
                validation_ms += elapsed
                error_text = str(error)
                validation_errors.append(f"attempt {attempts}: {error_text}")
                _log(
                    request_id,
                    "validation",
                    elapsed,
                    retries=attempts - 1,
                    result="retry",
                )
                active_prompt = (
                    f"{user_prompt}\n\nYour previous output failed validation. Correct every "
                    f"reported issue and return the complete LayoutProject again:\n{error_text}"
                )
                continue
            elapsed = _milliseconds(started)
            validation_ms += elapsed
            _log(
                request_id,
                "validation",
                elapsed,
                retries=attempts - 1,
                result="completed",
            )
            break

        if final_layout is None:
            _log(
                request_id,
                "pipeline",
                _milliseconds(total_started),
                retries=max(attempts - 1, 0),
                result="failed",
            )
            raise PipelineGenerationError(validation_errors)

        timing_ms = {
            "retrieval": retrieval_ms,
            "reranking": reranking_ms,
            "generation": generation_ms,
            "validation": validation_ms,
            "total": _milliseconds(total_started),
        }
        _log(
            request_id,
            "pipeline",
            timing_ms["total"],
            retries=attempts - 1,
            result="completed",
        )
        return PipelineResult(
            layout=final_layout,
            timing_ms=timing_ms,
            retries=attempts - 1,
            retrieval_result=retrieval_result,
            reranked_candidates=reranked_candidates,
            selected_context=selected_context,
            raw_response=raw_response,
            validation_errors=validation_errors,
        )


@cache
def get_allowed_fonts() -> tuple[str, ...]:
    return tuple(load_allowed_fonts(AppConfig.FONT_LIST_PATH))


@cache
def get_retrieval_service() -> RetrievalService:
    return RetrievalService()


@cache
def get_reranker_service() -> RerankerService:
    return RerankerService()


@cache
def get_generation_service() -> GenerationService:
    return GenerationService()


@cache
def get_validation_service() -> ValidationService:
    return ValidationService(
        get_allowed_fonts(),
        safe_margin=AppConfig.SAFE_MARGIN,
        image_bleed=AppConfig.IMAGE_BLEED,
        ad_tolerance=AppConfig.AD_BOUNDARY_TOLERANCE,
    )


@cache
def get_special_case_service() -> SpecialCaseService:
    return SpecialCaseService()


@cache
def get_pipeline_service() -> LayoutPipeline:
    return LayoutPipeline()
