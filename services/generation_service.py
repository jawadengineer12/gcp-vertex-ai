import json
import logging

from google.genai import types

from core.config import GENERATION_MODEL, GENERATION_TEMPERATURE
from core.vertex_client import get_vertex_client
from core.logger import get_logger

LOGGER = get_logger(__name__)


SYSTEM_INSTRUCTION = (
    "You are an expert AI layout engineering backend assistant.\n"
    "Your sole task is to generate structural layout data based on the provided user design brief.\n"
    "CRITICAL RULES:\n"
    "1. Return ONLY a raw JSON structure matching your target layout schema rules.\n"
    "2. Do NOT include any markdown code blocks, backticks (such as ```json), or wrapping symbols.\n"
    "3. Do NOT include any conversational text, descriptions, introductions, or closing remarks.\n"
    "4. Start your response directly with '{' and end exactly with '}'.\n"
    "5. Emphasize that element positions/size fields are allowed to extend outside page boundaries for bleeds."
)


def build_context_string(matched_context_examples: list[dict]) -> str:
    return "\n\n".join([
        (
            f"Matched Design Example (Page Index {ex['pageIndex']}):\n"
            f"{json.dumps(ex['expected_layout_json'], indent=2)}"
        )
        for ex in matched_context_examples
    ])


def generate_layout(user_prompt: str, matched_context_examples: list[dict]) -> str | None:
    LOGGER.info(
        "Starting layout generation | model=%s | context_examples=%s",
        GENERATION_MODEL,
        len(matched_context_examples),
    )

    client = get_vertex_client()
    context_string = build_context_string(matched_context_examples)

    combined_prompt = (
        "Use the following structural design references for scaling, rules, and alignment patterns:\n"
        f"{context_string}\n\n"
        "Now, generate a brand new layout specification for this designer instruction:\n"
        f"\"{user_prompt}\""
    )

    LOGGER.info("Sending prompt to Gemini via Vertex AI.")
    LOGGER.debug("Combined generation prompt:\n%s", combined_prompt)

    try:
        response = client.models.generate_content(
            model=GENERATION_MODEL,
            contents=combined_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=GENERATION_TEMPERATURE,
            ),
        )

        LOGGER.info("Gemini response received.")
        return response.text

    except Exception as e:
        LOGGER.exception("Stage 2 inference failed.")
        print(f"\n[ERROR]: Stage 2 Inference failed: {str(e)}")
        return None
