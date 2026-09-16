"""Gemini generation of complete converter-facing LayoutProject documents."""

import json
import logging
from dataclasses import asdict

from google.genai import types

from core.config import AppConfig
from core.vertex_client import get_vertex_client
from schemas.layout_schema import LayoutProject
from services.layout_plan_service import LayoutFeaturePlan

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are an expert print-layout JSON generator.
Return only one raw JSON object matching the supplied LayoutProject JSON schema.
Do not use Markdown fences or conversational text.
The root pageIndex is always 0. Child pageIndex values start at 1 and are sequential.
Use one page for covers unless the request explicitly requires more. Obey explicit page
counts. Use multiple pages for a full article only when the prompt clearly needs them.
Never invent names, dates, organizations, copy, or image URLs. Use the supplied collected
information verbatim, including placeholders.
Only https:// image URLs or [field_name_url] placeholders are valid. Never emit local,
file://, gs://, or operating-system paths.
Text frames stay inside the 0.25-inch safe margin. Images may extend exactly 0.125 inches
for bleed. Text frames must not overlap each other; image/text overlap is permitted.
Use only an approved exact font name. Font names contain the two literal characters \\t,
not an actual tab. Article content contains only textBody. Place columns, gutterSize,
margins, and textStyle beside content on the Article asset.
Do not add continuation metadata. Split continuation text between page Article assets.
"""


def _relationship_instruction(plan: LayoutFeaturePlan) -> str:
    instructions: list[str] = []
    if plan.threaded_text:
        instructions.append(
            "When threaded text is requested, create at least two linked Article frames. "
            "Put one shared articleDocumentLink inside each content object. The head uses "
            "expand=false and contains the complete textBody. Every continuation uses "
            "expand=true with an empty textBody so InDesign performs the flow. "
            "Every linked frame must use textStyle.autoFit=false so its geometry stays "
            "fixed and overflow reaches the continuation frame. "
            f"Thread scope: {plan.text_thread_scope}."
        )
        if plan.article_constraints:
            instructions.append(
                "ARTICLE FRAME CONSTRAINTS are resolved hard requirements. Match each "
                "listed page's start_y, height, and columns when those values are present."
            )
    if plan.image_spread:
        instructions.append(
            f"Create one cross-page Image on even page {plan.spread_start_page}; its width "
            f"must cross into page {plan.spread_end_page}. Include the target page but do "
            "not duplicate the image there. This is an intentional spread, not normal bleed."
        )
    return "\n".join(instructions)


def _system_instruction(plan: LayoutFeaturePlan) -> str:
    instruction = SYSTEM_INSTRUCTION
    if plan.threaded_text:
        instruction = instruction.replace(
            "Article content contains only textBody. ", ""
        ).replace(
            "Do not add continuation metadata. Split continuation text between page "
            "Article assets.\n",
            "",
        )
    relationship = _relationship_instruction(plan)
    return instruction + relationship if relationship else instruction


class GenerationService:
    def __init__(self) -> None:
        self.model = AppConfig.GENERATION_MODEL
        self.temperature = AppConfig.GEMINI_TEMPERATURE

    def generate_layout_json(
        self,
        active_prompt: str,
        context_examples: list[dict],
        collected_fields: dict[str, str],
        allowed_fonts: list[str],
        template: dict | None = None,
        layout_plan: LayoutFeaturePlan | None = None,
    ) -> str | None:
        plan = layout_plan or LayoutFeaturePlan()
        schema = LayoutProject.model_json_schema()
        safe_template = {
            key: value for key, value in (template or {}).items() if key != "_source"
        }
        context_string = "\n\n".join(
            (
                "Special Case Description:\n"
                f"{example['special_case_description']}\n\nExample JSON:\n"
                f"{json.dumps(example.get('expected_layout_json'), ensure_ascii=False)}"
                if example.get("special_case_description")
                else f"Reference page {example.get('pageIndex')}:\n"
                f"{json.dumps(example.get('expected_layout_json'), ensure_ascii=False)}"
            )
            for example in context_examples
        )
        relationship_context = (
            "INTERNAL LAYOUT RELATIONSHIPS (constraints only; never emit this object):\n"
            f"{json.dumps(asdict(plan), ensure_ascii=False)}\n\n"
            if plan.threaded_text or plan.image_spread
            else ""
        )
        combined_prompt = (
            "TARGET JSON SCHEMA:\n"
            f"{json.dumps(schema, ensure_ascii=False)}\n\n"
            "APPROVED FONT NAMES (choose only from this list):\n"
            f"{json.dumps(allowed_fonts, ensure_ascii=False)}\n\n"
            "TEMPLATE CONFIGURATION:\n"
            f"{json.dumps(safe_template, ensure_ascii=False)}\n\n"
            "COLLECTED USER INFORMATION:\n"
            f"{json.dumps(collected_fields, ensure_ascii=False)}\n\n"
            "SANITIZED STRUCTURAL REFERENCES (patterns only; do not copy their content):\n"
            f"{context_string}\n\n"
            f"{relationship_context}"
            "DESIGN REQUEST:\n"
            f"{active_prompt}"
        )
        try:
            response = get_vertex_client().models.generate_content(
                model=self.model,
                contents=combined_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_system_instruction(plan),
                    temperature=self.temperature,
                    response_mime_type="application/json",
                ),
            )
            return response.text
        except Exception:
            logger.exception("Gemini generation failed")
            return None
