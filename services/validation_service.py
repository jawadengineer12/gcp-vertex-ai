"""Parsing and quality validation for converter-compatible LayoutProject JSON."""

import json
import logging
from collections.abc import Iterable

from pydantic import ValidationError

from schemas.layout_schema import ArticleAsset, LayoutProject
from services.layout_plan_service import LayoutFeaturePlan
from services.relationship_validation_service import RelationshipValidationService

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

    def validate_payload(
        self, raw_payload: str | dict, layout_plan: LayoutFeaturePlan | None = None
    ) -> dict:
        """Parse, strictly validate, apply quality rules, and return canonical data."""
        json_data = self._parse(raw_payload)
        try:
            project = LayoutProject.model_validate(json_data)
        except ValidationError as error:
            logger.error("LayoutProject schema validation failed")
            raise

        plan = layout_plan or LayoutFeaturePlan()
        errors = RelationshipValidationService().errors(project, plan)
        errors.extend(self._quality_errors(project, plan))
        errors.extend(self._constraint_errors(project, plan))
        if errors:
            raise LayoutQualityError("\n".join(errors))

        logger.info("LayoutProject validation passed | pages=%d", len(project.pages))
        return project.model_dump(mode="json", exclude_none=True)

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

    def _quality_errors(
        self, project: LayoutProject, plan: LayoutFeaturePlan
    ) -> list[str]:
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
                            f"{label}: Article frame ({left}, {top}, "
                            f"{asset.size.width}, {asset.size.height}) must remain inside "
                            f'the {self.safe_margin}" safe margin; maximum legal width '
                            f"from this X is {max(width - self.safe_margin - left, 0):.4g} "
                            f"and maximum legal height from this Y is "
                            f"{max(height - self.safe_margin - top, 0):.4g}"
                        )
                    font = asset.textStyle.fontFamily
                    if font not in self.allowed_fonts:
                        errors.append(f"{label}: unapproved fontFamily {font!r}")
                else:
                    tolerance = (
                        self.image_bleed if asset.assetType == "Image" else self.ad_tolerance
                    )
                    intentional_spread = (
                        plan.image_spread
                        and asset.assetType == "Image"
                        and page.pageIndex == plan.spread_start_page
                        and right > width
                    )
                    if (
                        left < -tolerance
                        or top < -tolerance
                        or (right > width + tolerance and not intentional_spread)
                        or bottom > height + tolerance
                    ):
                        errors.append(
                            f"{label}: {asset.assetType} exceeds the allowed "
                            f'{tolerance}" page extension'
                        )

            errors.extend(self._article_overlap_errors(page.pageIndex, articles))
        return errors

    @staticmethod
    def _constraint_errors(
        project: LayoutProject, plan: LayoutFeaturePlan
    ) -> list[str]:
        errors: list[str] = []
        pages = {page.pageIndex: page for page in project.pages}
        head_pages = {
            page.pageIndex
            for page in project.pages
            for asset in page.assets
            if isinstance(asset, ArticleAsset) and asset.expand is False
        }
        for constraint in plan.article_constraints:
            page = pages.get(constraint.page_index)
            if page is None:
                errors.append(
                    f"Article constraint requires missing page {constraint.page_index}"
                )
                continue
            linked = [
                asset
                for asset in page.assets
                if isinstance(asset, ArticleAsset) and asset.expand is not None
            ]
            expected_expand = constraint.page_index not in head_pages
            matches = [asset for asset in linked if asset.expand is expected_expand]
            if not matches:
                errors.append(
                    f"page {constraint.page_index} has no threaded Article frame for its "
                    "explicit constraints"
                )
                continue
            asset = matches[0]
            for name, actual, expected in (
                ("startY", asset.position.startY, constraint.start_y),
                ("height", asset.size.height, constraint.height),
                ("columns", asset.columns, constraint.columns),
            ):
                if expected is not None and abs(actual - expected) > 0.001:
                    errors.append(
                        f"page {constraint.page_index} threaded Article {name} must be "
                        f"{expected}; got {actual}"
                    )
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
