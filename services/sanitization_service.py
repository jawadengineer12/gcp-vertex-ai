"""Normalize retrieved legacy examples before they are shown to Gemini."""

from copy import deepcopy
from pathlib import PurePosixPath, PureWindowsPath


ARTICLE_FIELDS = ("columns", "gutterSize", "margins", "textStyle")


def sanitize_retrieved_examples(
    candidates: list[dict], allowed_fonts: list[str]
) -> list[dict]:
    sanitized = deepcopy(candidates)
    for candidate in sanitized:
        layout = candidate.get("expected_layout_json")
        if isinstance(layout, dict):
            _normalize_layout(layout, allowed_fonts)
    return sanitized


def _normalize_layout(layout: dict, allowed_fonts: list[str]) -> None:
    pages = layout.get("pages")
    page_objects = pages if isinstance(pages, list) else [layout]
    for page in page_objects:
        if not isinstance(page, dict):
            continue
        for asset in page.get("assets", []):
            if not isinstance(asset, dict):
                continue
            content = asset.setdefault("content", {})
            if not isinstance(content, dict):
                continue
            if asset.get("assetType") == "Article":
                for field in ARTICLE_FIELDS:
                    if field in asset and field not in content:
                        content[field] = asset.pop(field)
                style = content.get("textStyle")
                if isinstance(style, dict) and isinstance(style.get("fontFamily"), str):
                    style["fontFamily"] = _approved_font(
                        style["fontFamily"], allowed_fonts
                    )
            elif "imageUrl" in content and _is_local_path(str(content["imageUrl"])):
                content["imageUrl"] = "[image_asset_reference_url]"


def _approved_font(value: str, allowed_fonts: list[str]) -> str:
    if value in allowed_fonts:
        return value
    family = value.split("\\t", 1)[0].strip().casefold()
    regular_match = next(
        (
            font
            for font in allowed_fonts
            if font.casefold() == f"{family}\\tregular"
        ),
        None,
    )
    if regular_match:
        return regular_match
    family_match = next(
        (font for font in allowed_fonts if font.split("\\t", 1)[0].casefold() == family),
        None,
    )
    return family_match or allowed_fonts[0]


def _is_local_path(value: str) -> bool:
    stripped = value.strip()
    if stripped.startswith(("https://", "[")):
        return False
    if stripped.startswith(("gs://", "file://", "/", "\\\\")):
        return True
    return PureWindowsPath(stripped).drive != "" or PurePosixPath(stripped).is_absolute()
