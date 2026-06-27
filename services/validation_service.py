# services/validation_service.py
"""
Validation service.

The original working main.py validates Gemini output as a single Page:
    Page(**final_json_data)

This is correct because Gemini is prompted to return a single-page JSON:
    { "pageIndex": <int>, "assets": [...] }

LayoutProject (with projectInfo / documentSettings / pages) is NOT what
Gemini returns. Do not validate against LayoutProject here.
"""
import json
import logging
from pydantic import ValidationError
from schemas.layout_schema import Page

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Validates the raw Gemini text response against the Page schema.
    """

    @staticmethod
    def validate_payload(raw_text: str) -> dict:
        """
        Parses and validates raw Gemini output.

        - Strips accidental markdown fences (```json ... ```)
        - Parses JSON
        - Validates against Page schema
        - Returns the validated dict on success
        - Raises json.JSONDecodeError or ValidationError on failure (caller handles retry)
        """
        cleaned = raw_text.strip()

        # Strip markdown code fences if Gemini leaked them despite instructions
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Drop the opening fence line (e.g. ```json or ```)
            lines = lines[1:]
            # Drop the closing fence if present
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            json_data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("JSON parse failed: %s", str(e))
            raise

        try:
            Page(**json_data)
        except ValidationError as e:
            logger.error("Schema validation failed: %s", str(e))
            raise

        logger.info("Validation passed.")
        return json_data
