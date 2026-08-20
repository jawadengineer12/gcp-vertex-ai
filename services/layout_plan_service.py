"""Deterministic detection of relationship-aware layout features."""

import re
from dataclasses import dataclass
from typing import Literal


ThreadScope = Literal["same_page", "cross_page"]


@dataclass(frozen=True)
class LayoutFeaturePlan:
    threaded_text: bool = False
    text_thread_scope: ThreadScope | None = None
    image_spread: bool = False
    spread_start_page: int | None = None
    spread_end_page: int | None = None


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

    def plan(self, prompt: str) -> LayoutFeaturePlan:
        cross_page = bool(self.CROSS_PAGE_PATTERN.search(prompt))
        threaded_text = cross_page or bool(self.THREAD_PATTERN.search(prompt))
        image_spread = bool(self.SPREAD_PATTERN.search(prompt))
        start_page = end_page = None
        if image_spread:
            match = self.PAGE_PAIR_PATTERN.search(prompt)
            start_page, end_page = (
                (int(match.group(1)), int(match.group(2))) if match else (2, 3)
            )
        return LayoutFeaturePlan(
            threaded_text=threaded_text,
            text_thread_scope=("cross_page" if cross_page else "same_page")
            if threaded_text
            else None,
            image_spread=image_spread,
            spread_start_page=start_page,
            spread_end_page=end_page,
        )
