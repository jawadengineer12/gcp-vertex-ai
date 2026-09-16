"""Deterministic detection of relationship-aware layout features."""

import re
from dataclasses import dataclass
from typing import Literal


ThreadScope = Literal["same_page", "cross_page"]


@dataclass(frozen=True)
class ArticleFrameConstraint:
    page_index: int
    start_y: float | None = None
    height: float | None = None
    columns: int | None = None


@dataclass(frozen=True)
class LayoutFeaturePlan:
    threaded_text: bool = False
    text_thread_scope: ThreadScope | None = None
    image_spread: bool = False
    spread_start_page: int | None = None
    spread_end_page: int | None = None
    article_constraints: tuple[ArticleFrameConstraint, ...] = ()


class LayoutPlanService:
    THREAD_PATTERN = re.compile(
        r"\b(?:continue text|overflow text|flow into another box|linked text frames?|"
        r"continue (?:the )?article|continue (?:the )?story into (?:another |the )?frame|"
        r"overflow into (?:another |the )?(?:box|frame|lower box)|"
        r"flow (?:text|article|story) into (?:another |the )?(?:box|frame))\b",
        re.IGNORECASE,
    )
    CROSS_PAGE_PATTERN = re.compile(
        r"\b(?:continue(?: (?:text|article|story))? (?:on|to) (?:the )?next page|"
        r"continue (?:the )?(?:text|article|story) (?:in|on) (?:the )?"
        r"(?:second|following|next) page|"
        r"flow (?:text|article|story) to (?:the )?next page|"
        r"overflow to (?:the )?next page|"
        r"article continues? on (?:the )?following page)\b",
        re.IGNORECASE,
    )
    SPREAD_PATTERN = re.compile(
        r"\b(?:two[ -]page (?:image )?spread|facing pages|image across pages|"
        r"image spanning pages|spread image|extend (?:the )?image into (?:the )?facing page|"
        r"full width across pages|panoramic image (?:over|across) both pages)\b",
        re.IGNORECASE,
    )
    PAGE_PAIR_PATTERN = re.compile(
        r"\bpages?\s+(\d+)\s+(?:and|to|through|-)\s+(?:page\s+)?(\d+)\b",
        re.IGNORECASE,
    )
    PAGE_REFERENCE_PATTERN = re.compile(
        r"\b(?:page\s*(\d+)|(?:the\s+)?(first|second|third|fourth|fifth)\s+page)\b",
        re.IGNORECASE,
    )
    START_Y_PATTERN = re.compile(
        r"(?:below\s+)?(\d+(?:\.\d+)?)\s*(?:inches?|\")\s+"
        r"(?:from\s+(?:on\s+)?|below\s+)?(?:the\s+)?top\b",
        re.IGNORECASE,
    )
    HEIGHT_PATTERN = re.compile(
        r"\b(?:height(?:\s+of)?\s*(\d+(?:\.\d+)?)\s*(?:inches?|\")|"
        r"(\d+(?:\.\d+)?)\s*(?:inches?|\")\s+in\s+height)\b",
        re.IGNORECASE,
    )
    COLUMNS_PATTERN = re.compile(r"\b(\d+)\s+columns?\b", re.IGNORECASE)
    ORDINAL_PAGES = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}

    def plan(
        self,
        prompt: str,
        template: dict | None = None,
        safe_margin: float = 0.25,
    ) -> LayoutFeaturePlan:
        cross_page = bool(self.CROSS_PAGE_PATTERN.search(prompt))
        threaded_text = cross_page or bool(self.THREAD_PATTERN.search(prompt))
        image_spread = bool(self.SPREAD_PATTERN.search(prompt))
        start_page = end_page = None
        if image_spread:
            match = self.PAGE_PAIR_PATTERN.search(prompt)
            start_page, end_page = (
                (int(match.group(1)), int(match.group(2))) if match else (2, 3)
            )
        constraints = (
            self._article_constraints(prompt, template, safe_margin)
            if threaded_text
            else ()
        )
        return LayoutFeaturePlan(
            threaded_text=threaded_text,
            text_thread_scope=("cross_page" if cross_page else "same_page")
            if threaded_text
            else None,
            image_spread=image_spread,
            spread_start_page=start_page,
            spread_end_page=end_page,
            article_constraints=constraints,
        )

    def _article_constraints(
        self, prompt: str, template: dict | None, safe_margin: float
    ) -> tuple[ArticleFrameConstraint, ...]:
        settings = (template or {}).get("defaultSettings", {})
        page_height = float(settings.get("pageHeight", 11.0))
        margin = float(settings.get("margin", safe_margin))
        usable_bottom = page_height - margin
        constraints: list[ArticleFrameConstraint] = []
        last_page: int | None = None

        for sentence in re.split(
            r"(?<=[.!?])\s+|\n+|(?i:\band\s+(?=continue\b))", prompt
        ):
            if re.search(r"\bimage\b", sentence, re.IGNORECASE) and not re.search(
                r"\b(?:text|article|story|columns?)\b", sentence, re.IGNORECASE
            ):
                continue
            start_match = self.START_Y_PATTERN.search(sentence)
            height_match = self.HEIGHT_PATTERN.search(sentence)
            columns_match = self.COLUMNS_PATTERN.search(sentence)
            if not any((start_match, height_match, columns_match)):
                continue

            page_match = self.PAGE_REFERENCE_PATTERN.search(sentence)
            if page_match:
                page = (
                    int(page_match.group(1))
                    if page_match.group(1)
                    else self.ORDINAL_PAGES[page_match.group(2).casefold()]
                )
            elif re.search(r"\b(?:next|following) page\b", sentence, re.IGNORECASE):
                page = (last_page or 1) + 1
            elif re.search(r"\bcontinue\b", sentence, re.IGNORECASE):
                page = (last_page or 1) + 1
            elif re.search(r"\b(?:begin|start|place)\b", sentence, re.IGNORECASE):
                page = last_page or 1
            else:
                continue
            last_page = page

            start_y = float(start_match.group(1)) if start_match else None
            if start_y is not None:
                start_y = min(max(start_y, margin), usable_bottom - 0.01)
            height = None
            if height_match:
                height = float(height_match.group(1) or height_match.group(2))
                available = usable_bottom - (start_y if start_y is not None else margin)
                height = min(height, available)
            constraints.append(
                ArticleFrameConstraint(
                    page_index=page,
                    start_y=round(start_y, 4) if start_y is not None else None,
                    height=round(height, 4) if height is not None else None,
                    columns=int(columns_match.group(1)) if columns_match else None,
                )
            )
        return tuple(constraints)
