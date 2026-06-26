# services/generation_service.py
import logging
from google.genai import types
from config.config import AppConfig
from core.vertex_client import vertex_client

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "You are an expert AI layout engineering backend assistant.\n"
    "Your sole task is to generate structural layout data based on the provided user design brief.\n"
    "CRITICAL RULES:\n"
    "1. Return ONLY a raw JSON structure matching your target layout schema rules.\n"
    "2. Do NOT include any markdown code blocks, backticks (such as ```json), or wrapping symbols.\n"
    "3. Do NOT include any conversational text, descriptions, introductions, or closing remarks.\n"
    "4. Start your response directly with '{' and end exactly with '}'.\n"
    "5. Element positions and size fields are allowed to extend outside page boundaries for bleeds.\n"
    "6. The output must be a single JSON object with keys: 'pageIndex' (int) and 'assets' (list)."
)


class GenerationService:
    """
    Queries the Gemini model via Vertex AI to generate layout JSON.
    """

    def __init__(self) -> None:
        self.model = AppConfig.GENERATION_MODEL
        self.temperature = AppConfig.GEMINI_TEMPERATURE
        logger.info(
            "GenerationService initialized | model=%s | temperature=%.2f",
            self.model,
            self.temperature,
        )

    def generate_layout_json(
        self, active_prompt: str, context_examples: list[dict]
    ) -> str | None:
        """
        Sends the user prompt and retrieved context examples to Gemini.
        Returns the raw text response or None on failure.
        """
        context_string = "\n\n".join([
            f"Matched Design Example (Page Index {ex['pageIndex']}):\n"
            f"{ex['expected_layout_json']}"
            for ex in context_examples
        ])

        combined_prompt = (
            f"Use the following structural design references for scaling, rules, and alignment patterns:\n"
            f"{context_string}\n\n"
            f"Now, generate a brand new layout specification for this designer instruction:\n"
            f"\"{active_prompt}\""
        )

        logger.info(
            "Sending prompt to Gemini | model=%s | context_examples=%d",
            self.model,
            len(context_examples),
        )

        try:
            response = vertex_client.models.generate_content(
                model=self.model,
                contents=combined_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=self.temperature,
                ),
            )
            logger.info("Gemini response received | length=%d",
                        len(response.text or ""))
            return response.text

        except Exception as e:
            logger.error("Gemini generation failed: %s", str(e))
            return None
