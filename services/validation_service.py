"""Parsing and quality validation for converter-compatible LayoutProject JSON."""

import json
import logging
from collections.abc import Iterable

from pydantic import ValidationError

from schemas.layout_schema import ArticleAsset, LayoutProject

logger = logging.getLogger(__name__)


class LayoutQualityError(ValueError):
    """Raised when valid schema data violates layout production rules."""


class ValidationService:
    def __init__(
        self,
        allowed_fonts: Iterable[str],
        safe_margin: float = 0.25,
        image_bleed: float = 0.125,
        ad_tolerance: float = 0.5,
    ) -> None:
        self.allowed_fonts = frozenset(allowed_fonts)
        if not self.allowed_fonts:
            raise ValueError("Font validation requires at least one approved font")
        self.safe_margin = safe_margin
        self.image_bleed = image_bleed
        self.ad_tolerance = ad_tolerance

    def validate_payload(self, raw_payload: str | dict) -> dict:
        """Parse, strictly validate, apply quality rules, and return canonical data."""
        json_data = self._parse(raw_payload)
        try:
            project = LayoutProject.model_validate(json_data)
        except ValidationError as error:
            logger.error("LayoutProject schema validation failed: %s", error)
            raise

        errors = self._quality_errors(project)
        if errors:
            raise LayoutQualityError("\n".join(errors))

        logger.info("LayoutProject validation passed | pages=%d", len(project.pages))
        return project.model_dump(mode="json")

    @staticmethod
    def _parse(raw_payload: str | dict) -> dict:
        if isinstance(raw_payload, dict):
            return raw_payload
        cleaned = raw_payload.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines.pop()
            cleaned = "\n".join(lines).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.exception("JSON parse failed")
            raise
        if not isinstance(parsed, dict):
            raise TypeError("Gemini response must be a JSON object")
        return parsed

    def _quality_errors(self, project: LayoutProject) -> list[str]:
        errors: list[str] = []
        width = project.documentSettings.pageWidth
        height = project.documentSettings.pageHeight

        for page in project.pages:
            articles: list[tuple[int, ArticleAsset]] = []
            for asset_index, asset in enumerate(page.assets):
                label = f"pages[{page.pageIndex}].assets[{asset_index}]"
                left = asset.position.startX
                top = asset.position.startY
                right = left + asset.size.width
                bottom = top + asset.size.height

                if asset.assetType == "Article":
                    articles.append((asset_index, asset))
                    if (
                        left < self.safe_margin
                        or top < self.safe_margin
                        or right > width - self.safe_margin
                        or bottom > height - self.safe_margin
                    ):
                        errors.append(
                            f"{label}: Article frame must remain inside the "
                            f'{self.safe_margin}" safe margin'
                        )
                    font = asset.textStyle.fontFamily
                    if font not in self.allowed_fonts:
                        errors.append(f"{label}: unapproved fontFamily {font!r}")
                else:
                    tolerance = (
                        self.image_bleed if asset.assetType == "Image" else self.ad_tolerance
                    )
                    if (
                        left < -tolerance
                        or top < -tolerance
                        or right > width + tolerance
                        or bottom > height + tolerance
                    ):
                        errors.append(
                            f"{label}: {asset.assetType} exceeds the allowed "
                            f'{tolerance}" page extension'
                        )

            errors.extend(self._article_overlap_errors(page.pageIndex, articles))
        return errors

    @staticmethod
    def _article_overlap_errors(
        page_index: int, articles: list[tuple[int, ArticleAsset]]
    ) -> list[str]:
        errors: list[str] = []
        for offset, (left_index, left_asset) in enumerate(articles):
            for right_index, right_asset in articles[offset + 1 :]:
                horizontal = min(
                    left_asset.position.startX + left_asset.size.width,
                    right_asset.position.startX + right_asset.size.width,
                ) - max(left_asset.position.startX, right_asset.position.startX)
                vertical = min(
                    left_asset.position.startY + left_asset.size.height,
                    right_asset.position.startY + right_asset.size.height,
                ) - max(left_asset.position.startY, right_asset.position.startY)
                if horizontal > 0 and vertical > 0:
                    errors.append(
                        f"pages[{page_index}]: Article assets {left_index} and "
                        f"{right_index} overlap"
                    )
        return errors
