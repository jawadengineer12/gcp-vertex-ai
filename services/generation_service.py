"""Gemini generation of complete converter-facing LayoutProject documents."""

import json
import logging

from google.genai import types

from core.config import AppConfig
from core.vertex_client import vertex_client
from schemas.layout_schema import LayoutProject

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
    ) -> str | None:
        schema = LayoutProject.model_json_schema()
        safe_template = {
            key: value for key, value in (template or {}).items() if key != "_source"
        }
        context_string = "\n\n".join(
            f"Reference page {example.get('pageIndex')}:\n"
            f"{json.dumps(example.get('expected_layout_json'), ensure_ascii=False)}"
            for example in context_examples
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
            "DESIGN REQUEST:\n"
            f"{active_prompt}"
        )
        try:
            response = vertex_client.models.generate_content(
                model=self.model,
                contents=combined_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=self.temperature,
                    response_mime_type="application/json",
                ),
            )
            return response.text
        except Exception:
            logger.exception("Gemini generation failed")
            return None
