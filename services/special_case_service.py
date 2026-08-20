"""Load confirmed relationship-aware examples without changing normal retrieval."""

import json
from pathlib import Path

from core.config import AppConfig
from services.layout_plan_service import LayoutFeaturePlan


class SpecialCaseService:
    def __init__(self, path: Path = AppConfig.SPECIAL_CASE_LIBRARY_PATH) -> None:
        self.cases = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def context_for(self, plan: LayoutFeaturePlan) -> list[dict]:
        features = {
            feature
            for feature, enabled in (
                ("threaded_text", plan.threaded_text),
                ("image_spread", plan.image_spread),
            )
            if enabled
        }
        return [
            {
                "natural_language_intent": case["description"],
                "special_case_description": case["description"]
                + "\nRules: "
                + "; ".join(case["rules"]),
                "expected_layout_json": case["example"],
            }
            for case in self.cases
            if case.get("feature") in features
        ]
