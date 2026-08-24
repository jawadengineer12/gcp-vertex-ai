"""Semantic validation for relationships that ordinary geometry cannot express."""

from schemas.layout_schema import ArticleAsset, LayoutProject
from services.layout_plan_service import LayoutFeaturePlan


class RelationshipValidationService:
    def errors(self, project: LayoutProject, plan: LayoutFeaturePlan) -> list[str]:
        errors: list[str] = []
        if plan.threaded_text:
            errors.extend(self._thread_errors(project, plan))
        if plan.image_spread:
            errors.extend(self._spread_errors(project, plan))
        return errors

    @staticmethod
    def _thread_errors(
        project: LayoutProject, plan: LayoutFeaturePlan
    ) -> list[str]:
        frames: list[tuple[int, int, ArticleAsset]] = [
            (page.pageIndex, index, asset)
            for page in project.pages
            for index, asset in enumerate(page.assets)
            if isinstance(asset, ArticleAsset)
            and (asset.expand is not None or asset.content.articleDocumentLink is not None)
        ]
        if len(frames) < 2:
            return ["threaded text requires at least two linked Article frames"]

        errors: list[str] = []
        links = {asset.content.articleDocumentLink for _, _, asset in frames}
        if None in links or len(links) != 1:
            errors.append("all threaded Article frames must share one articleDocumentLink")
        heads = [frame for frame in frames if frame[2].expand is False]
        continuations = [frame for frame in frames if frame[2].expand is True]
        if len(heads) != 1:
            errors.append("threaded text requires exactly one head frame with expand=false")
        elif not heads[0][2].content.textBody:
            errors.append("thread head frame must contain the complete textBody")
        if len(continuations) != len(frames) - 1:
            errors.append("every non-head threaded frame must use expand=true")
        if any(asset.content.textBody for _, _, asset in continuations):
            errors.append("thread continuation frames must have empty textBody")
        if any(asset.textStyle.autoFit for _, _, asset in frames):
            errors.append("threaded Article frames must use textStyle.autoFit=false")
        if heads and continuations:
            head_key = heads[0][:2]
            if any(frame[:2] <= head_key for frame in continuations):
                errors.append("thread continuation frames must follow the head frame")
            pages = {page for page, _, _ in frames}
            if plan.text_thread_scope == "same_page" and len(pages) != 1:
                errors.append("same-page threaded text must remain on one page")
            if plan.text_thread_scope == "cross_page" and not any(
                page > heads[0][0] for page, _, _ in continuations
            ):
                errors.append("cross-page threaded text requires a continuation on a later page")
        return errors

    @staticmethod
    def _spread_errors(
        project: LayoutProject, plan: LayoutFeaturePlan
    ) -> list[str]:
        start = plan.spread_start_page
        end = plan.spread_end_page
        if start is None or end is None:
            return ["image spread requires source and target pages"]
        if start % 2:
            return ["image spread must start on an even page"]
        if end != start + 1:
            return ["image spread target must immediately follow its source page"]

        pages = {page.pageIndex: page for page in project.pages}
        if start not in pages or end not in pages:
            return ["image spread source and target pages must exist"]
        width = project.documentSettings.pageWidth
        crossing = [
            asset
            for asset in pages[start].assets
            if asset.assetType == "Image"
            and asset.position.startX + asset.size.width > width
        ]
        if not crossing:
            return ["image spread source image must cross the page boundary"]
        source_urls = {asset.content.imageUrl for asset in crossing}
        if any(
            asset.assetType == "Image" and asset.content.imageUrl in source_urls
            for asset in pages[end].assets
        ):
            return ["image spread must not be duplicated on the target page"]
        return []
