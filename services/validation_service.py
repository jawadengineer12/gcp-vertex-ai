import json
from typing import Any

from pydantic import ValidationError

from schemas.layout_schema import Page
from core.logger import get_logger

LOGGER = get_logger(__name__)


def parse_json_response(raw_ai_response: str) -> dict[str, Any]:
    LOGGER.info("Parsing raw AI response into JSON.")

    try:
        parsed = json.loads(raw_ai_response.strip())
        LOGGER.info("AI response parsed successfully.")
        return parsed

    except json.JSONDecodeError:
        LOGGER.exception("AI response failed JSON parsing.")
        raise


def validate_layout_page(layout_data: dict[str, Any]) -> Page:
    LOGGER.info("Running Pydantic layout validation.")

    try:
        validated_layout = Page(**layout_data)
        LOGGER.info("Pydantic validation passed.")
        return validated_layout

    except ValidationError:
        LOGGER.exception("Pydantic validation failed.")
        raise


def parse_and_validate_layout(raw_ai_response: str) -> tuple[dict[str, Any], Page]:
    layout_data = parse_json_response(raw_ai_response)
    validated_layout = validate_layout_page(layout_data)
    return layout_data, validated_layout
