import json
import unittest
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from schemas.layout_schema import LayoutProject
from services.font_service import load_allowed_fonts
from services.generation_service import (
    GenerationService,
    SYSTEM_INSTRUCTION,
    _system_instruction,
)
from services.layout_plan_service import (
    ArticleFrameConstraint,
    LayoutFeaturePlan,
    LayoutPlanService,
)
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

    def test_prompt_variations_map_to_the_same_features(self) -> None:
        planner = LayoutPlanService()
        for prompt in (
            "two page spread",
            "extend image into facing page",
            "full width across pages 2 and 3",
            "panoramic image over both pages",
        ):
            with self.subTest(prompt=prompt):
                self.assertTrue(planner.plan(prompt).image_spread)

        for prompt, scope in (
            ("continue story into another frame", "same_page"),
            ("overflow into lower box", "same_page"),
            ("flow article to next page", "cross_page"),
        ):
            with self.subTest(prompt=prompt):
                plan = planner.plan(prompt)
                self.assertTrue(plan.threaded_text)
                self.assertEqual(plan.text_thread_scope, scope)

    def test_client_thread_geometry_is_parsed_and_clamped(self) -> None:
        prompt = (
            "Create a 2 page magazine article. Begin the text below 8 inches from "
            "the top of the first page formatted into 3 columns. Continue the text "
            "in the second page formatted into 2 columns that are 4 inches in height."
        )
        plan = LayoutPlanService().plan(prompt)
        self.assertEqual(plan.text_thread_scope, "cross_page")
        self.assertIn("autoFit=false", _system_instruction(plan))
        self.assertIn("resolved hard requirements", _system_instruction(plan))
        self.assertEqual(
            plan.article_constraints,
            (
                ArticleFrameConstraint(1, start_y=8.0, columns=3),
                ArticleFrameConstraint(2, height=4.0, columns=2),
            ),
        )

        clamped = LayoutPlanService().plan(
            "Continue text on the next page. On page 1 start 9 inches from the "
            "top with height 4 inches in 3 columns."
        )
        self.assertEqual(clamped.article_constraints[0].height, 1.75)

        minimal = LayoutPlanService().plan(
            "Begin text in 3 columns starting 9 inches from the top and continue "
            "text on the following page."
        )
        self.assertEqual(minimal.article_constraints[0].page_index, 1)
        self.assertEqual(minimal.article_constraints[0].start_y, 9.0)

        combined = LayoutPlanService().plan(
            "Place one image on page 2 with height 3 inches. Continue text on the "
            "following page in 2 columns."
        )
        self.assertNotIn(3.0, {item.height for item in combined.article_constraints})

    def test_image_field_names_do_not_collide(self) -> None:
        template = {
            "requiredFields": [
                {"name": "image_url", "question": "Template image", "type": "image"}
            ]
        }
        names = [
            field.name
            for field in RequirementAgent().resolve(
                "Add a hero image and a spread image", template
            )
        ]
        self.assertEqual(names, ["image_url", "hero_image_url", "spread_image_url"])
        self.assertEqual(len(names), len(set(names)))


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

    def test_thread_constraints_and_fixed_frames_are_enforced(self) -> None:
        head = article(0.25, "Full story", "story_004", False)
        head["position"]["startY"] = 9.0
        head["size"]["height"] = 1.75
        head["columns"] = 3
        continuation = article(0.25, "", "story_004", True)
        continuation["size"]["height"] = 4.0
        continuation["columns"] = 2
        payload = project(
            [
                {"pageIndex": 1, "assets": [head]},
                {"pageIndex": 2, "assets": [continuation]},
            ]
        )
        plan = LayoutFeaturePlan(
            threaded_text=True,
            text_thread_scope="cross_page",
            article_constraints=(
                ArticleFrameConstraint(1, start_y=9.0, height=1.75, columns=3),
                ArticleFrameConstraint(2, height=4.0, columns=2),
            ),
        )
        self.validator.validate_payload(payload, plan)

        payload["pages"][0]["assets"][0]["size"]["height"] = 1.76
        with self.assertRaisesRegex(LayoutQualityError, "maximum legal height"):
            self.validator.validate_payload(payload, plan)
        payload["pages"][0]["assets"][0]["size"]["height"] = 1.75
        payload["pages"][1]["assets"][0]["textStyle"]["autoFit"] = True
        with self.assertRaisesRegex(LayoutQualityError, "autoFit=false"):
            self.validator.validate_payload(payload, plan)

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

    def test_confirmed_special_library_examples_validate(self) -> None:
        validator = ValidationService(
            load_allowed_fonts(ROOT / "raw_data" / "Font List.csv")
        )
        for case in SpecialCaseService().cases:
            with self.subTest(case=case["case_id"]):
                plan = (
                    LayoutFeaturePlan(True, case["scope"])
                    if case["feature"] == "threaded_text"
                    else LayoutFeaturePlan(False, None, True, 2, 3)
                )
                validator.validate_payload(case["example"], plan)


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
                "Create a two-page image spread",
                context,
                {"image_2_url": "https://images.example/second.jpg"},
                [FONT],
                None,
                plan,
            )
        finally:
            module.get_vertex_client = original

        self.assertIn("Special Case Description:", fake.models.kwargs["contents"])
        self.assertIn("must not be duplicated", fake.models.kwargs["contents"])
        self.assertIn('"image_2_url"', fake.models.kwargs["contents"])
        self.assertNotIn('"image_url_2"', fake.models.kwargs["contents"])
        instruction = fake.models.kwargs["config"].system_instruction
        self.assertIn("intentional spread, not normal bleed", instruction)

    def test_thread_reference_scope_must_match_plan(self) -> None:
        service = SpecialCaseService()
        same_page = service.context_for(LayoutFeaturePlan(True, "same_page"))
        cross_page = service.context_for(LayoutFeaturePlan(True, "cross_page"))
        self.assertEqual(len(same_page), 1)
        self.assertEqual(cross_page, [])


class NormalRegressionTests(unittest.TestCase):
    def test_saved_normal_layouts_are_unchanged(self) -> None:
        fonts = load_allowed_fonts(ROOT / "raw_data" / "Font List.csv")
        validator = ValidationService(fonts)
        for path in sorted((ROOT / "baseline_outputs").glob("*.json")):
            with self.subTest(path=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(validator.validate_payload(payload), payload)


class GeneratedOutputAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = ValidationService(
            load_allowed_fonts(ROOT / "raw_data" / "Font List.csv")
        )

    @staticmethod
    def load(name: str) -> dict:
        return json.loads(
            (ROOT / "special_case_outputs" / name).read_text(encoding="utf-8")
        )

    def test_saved_same_page_thread_relationship(self) -> None:
        payload = self.load("same_page_threaded_text.json")
        self.validator.validate_payload(payload, LayoutFeaturePlan(True, "same_page"))
        linked = [
            asset
            for asset in payload["pages"][0]["assets"]
            if asset.get("content", {}).get("articleDocumentLink")
        ]
        self.assertEqual(len(linked), 2)
        self.assertEqual(
            {asset["content"]["articleDocumentLink"] for asset in linked},
            {"community_gardens_article"},
        )
        self.assertTrue(next(asset for asset in linked if not asset["expand"])["content"]["textBody"])
        self.assertEqual(next(asset for asset in linked if asset["expand"])["content"]["textBody"], "")

    def test_saved_cross_page_thread_relationship(self) -> None:
        payload = self.load("cross_page_threaded_text.json")
        self.validator.validate_payload(payload, LayoutFeaturePlan(True, "cross_page"))
        linked = [
            (page["pageIndex"], asset)
            for page in payload["pages"]
            for asset in page["assets"]
            if asset.get("content", {}).get("articleDocumentLink")
        ]
        self.assertEqual(len({asset["content"]["articleDocumentLink"] for _, asset in linked}), 1)
        self.assertEqual([page for page, asset in linked if not asset["expand"]], [1])
        self.assertTrue(any(page == 2 and asset["expand"] for page, asset in linked))
        self.assertTrue(
            all(not asset["content"]["textBody"] for _, asset in linked if asset["expand"])
        )

    def test_saved_spread_has_no_duplicate_and_target_is_usable(self) -> None:
        payload = self.load("image_spread.json")
        self.validator.validate_payload(
            payload, LayoutFeaturePlan(False, None, True, 2, 3)
        )
        page2, page3 = payload["pages"][1:3]
        crossing = [
            asset
            for asset in page2["assets"]
            if asset["assetType"] == "Image"
            and asset["position"]["startX"] + asset["size"]["width"] > 8.5
        ]
        self.assertEqual(len(crossing), 1)
        self.assertNotIn(
            crossing[0]["content"]["imageUrl"],
            {
                asset["content"]["imageUrl"]
                for asset in page3["assets"]
                if asset["assetType"] == "Image"
            },
        )
        self.assertTrue(page3["assets"])


if __name__ == "__main__":
    unittest.main()
