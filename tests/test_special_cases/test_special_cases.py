import json
import unittest
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from schemas.layout_schema import LayoutProject
from services.font_service import load_allowed_fonts
from services.generation_service import GenerationService, SYSTEM_INSTRUCTION, _system_instruction
from services.layout_plan_service import LayoutFeaturePlan, LayoutPlanService
from services.relationship_validation_service import RelationshipValidationService
from services.requirement_agent import RequirementAgent
from services.special_case_service import SpecialCaseService
from services.validation_service import LayoutQualityError, ValidationService
from scripts.normalize_special_case_library import normalize_cases


FONT = "Adobe Garamond Pro\\tRegular"
ROOT = Path(__file__).parents[2]


def article(x: float, page_text: str, link: str, expand: bool) -> dict:
    return {
        "assetType": "Article",
        "expand": expand,
        "position": {"startX": x, "startY": 0.25},
        "size": {"width": 3.5, "height": 5.0},
        "content": {"articleDocumentLink": link, "textBody": page_text},
        "columns": 1,
        "gutterSize": 0.2,
        "margins": {"top": 0.0, "left": 0.0, "bottom": 0.0, "right": 0.0},
        "textStyle": {
            "fontFamily": FONT,
            "fontSize": 10.0,
            "bold": False,
            "italic": False,
            "underline": False,
            "color": "#000000",
            "autoFit": False,
        },
    }


def project(pages: list[dict]) -> dict:
    return {
        "pageIndex": 0,
        "documentSettings": {"pageWidth": 8.5, "pageHeight": 11.0},
        "projectInfo": {"projectName": "Special case"},
        "pages": pages,
    }


class LayoutPlanTests(unittest.TestCase):
    def test_detects_only_explicit_relationship_phrases(self) -> None:
        planner = LayoutPlanService()
        same_page = planner.plan("Continue article into second box")
        self.assertTrue(same_page.threaded_text)
        self.assertEqual(same_page.text_thread_scope, "same_page")

        cross_page = planner.plan("Article continues on following page")
        self.assertEqual(cross_page.text_thread_scope, "cross_page")
        self.assertEqual(
            planner.plan("Continue text on the next page").text_thread_scope,
            "cross_page",
        )

        spread = planner.plan("Use a spread image across pages 2 and 3")
        self.assertEqual((spread.spread_start_page, spread.spread_end_page), (2, 3))
        self.assertFalse(planner.plan("Use a full bleed image").image_spread)

    def test_requirements_are_additive(self) -> None:
        template = {
            "requiredFields": [
                {"name": "article_title", "question": "Title"},
                {"name": "author_name", "question": "Author"},
            ]
        }
        names = {
            field.name
            for field in RequirementAgent().resolve(
                "Add two images and a spread image", template
            )
        }
        self.assertEqual(
            names,
            {"article_title", "author_name", "image_url", "image_2_url", "spread_image_url"},
        )


class RelationshipValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ValidationService([FONT])

    def test_same_page_thread(self) -> None:
        payload = project(
            [
                {
                    "pageIndex": 1,
                    "assets": [
                        article(0.25, "Complete article", "story_001", False),
                        article(4.0, "", "story_001", True),
                    ],
                }
            ]
        )
        plan = LayoutFeaturePlan(True, "same_page")
        result = self.validator.validate_payload(payload, plan)
        self.assertFalse(result["pages"][0]["assets"][0]["expand"])
        self.assertTrue(result["pages"][0]["assets"][1]["expand"])
        self.assertEqual(
            result["pages"][0]["assets"][0]["content"]["articleDocumentLink"],
            result["pages"][0]["assets"][1]["content"]["articleDocumentLink"],
        )
        payload["pages"][0]["assets"][0]["content"]["textBody"] = ""
        with self.assertRaisesRegex(LayoutQualityError, "head frame"):
            self.validator.validate_payload(payload, plan)

    def test_cross_page_thread(self) -> None:
        payload = project(
            [
                {"pageIndex": 1, "assets": [article(0.25, "Full story", "story_002", False)]},
                {"pageIndex": 2, "assets": [article(0.25, "", "story_002", True)]},
            ]
        )
        self.validator.validate_payload(payload, LayoutFeaturePlan(True, "cross_page"))

    def test_expand_is_a_json_boolean(self) -> None:
        payload = project(
            [{"pageIndex": 1, "assets": [article(0.25, "Story", "story_003", False)]}]
        )
        payload["pages"][0]["assets"][0]["expand"] = "false"
        with self.assertRaises(ValidationError):
            LayoutProject.model_validate(payload)

    def test_image_spread_and_invalid_odd_source(self) -> None:
        case = SpecialCaseService().cases[0]
        payload = deepcopy(case["example"])
        valid_plan = LayoutFeaturePlan(False, None, True, 2, 3)
        self.validator.validate_payload(payload, valid_plan)

        odd_plan = LayoutFeaturePlan(False, None, True, 1, 2)
        with self.assertRaisesRegex(LayoutQualityError, "even page"):
            self.validator.validate_payload(payload, odd_plan)

    def test_duplicate_spread_image_is_rejected(self) -> None:
        case = SpecialCaseService().cases[0]
        payload = deepcopy(case["example"])
        payload["pages"][2]["assets"] = [deepcopy(payload["pages"][1]["assets"][0])]
        parsed = LayoutProject.model_validate(payload)
        errors = RelationshipValidationService().errors(
            parsed, LayoutFeaturePlan(False, None, True, 2, 3)
        )
        self.assertTrue(any("duplicated" in error for error in errors))

    def test_special_normalization_preserves_empty_target_page(self) -> None:
        cases = SpecialCaseService().cases
        normalized = normalize_cases(cases, [FONT])
        self.assertEqual(normalized[0]["example"]["pages"][2]["assets"], [])


class GenerationContextTests(unittest.TestCase):
    def test_normal_generation_instruction_is_unchanged(self) -> None:
        self.assertEqual(_system_instruction(LayoutFeaturePlan()), SYSTEM_INSTRUCTION)

    def test_special_context_explains_relationship(self) -> None:
        import services.generation_service as module

        class Models:
            def generate_content(self, **kwargs):
                self.kwargs = kwargs
                return type("Response", (), {"text": "{}"})()

        fake = type("Client", (), {"models": Models()})()
        original = module.get_vertex_client
        module.get_vertex_client = lambda: fake
        try:
            plan = LayoutFeaturePlan(False, None, True, 2, 3)
            context = SpecialCaseService().context_for(plan)
            GenerationService().generate_layout_json(
                "Create a two-page image spread", context, {}, [FONT], None, plan
            )
        finally:
            module.get_vertex_client = original

        self.assertIn("Special Case Description:", fake.models.kwargs["contents"])
        self.assertIn("must not be duplicated", fake.models.kwargs["contents"])
        instruction = fake.models.kwargs["config"].system_instruction
        self.assertIn("intentional spread, not normal bleed", instruction)


class NormalRegressionTests(unittest.TestCase):
    def test_saved_normal_layouts_are_unchanged(self) -> None:
        fonts = load_allowed_fonts(ROOT / "raw_data" / "Font List.csv")
        validator = ValidationService(fonts)
        for path in sorted((ROOT / "baseline_outputs").glob("*.json")):
            with self.subTest(path=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(validator.validate_payload(payload), payload)


if __name__ == "__main__":
    unittest.main()
