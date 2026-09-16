import unittest

from services.requirement_agent import RequirementAgent
from services.information_agent import InformationAgent
from services.requirement_agent import RequiredField


class RequirementAgentImageDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = RequirementAgent()

    def test_visual_terms_request_an_image_url(self) -> None:
        terms = (
            "image",
            "photo",
            "photograph",
            "photography",
            "picture",
            "pic",
            "snapshot",
            "graphic",
            "illustration",
            "artwork",
            "cover art",
            "logo",
            "portrait",
            "headshot",
            "product shot",
            "screenshot",
            "scan",
            "thumbnail",
            "avatar",
            "icon",
            "banner",
            "poster",
            "drawing",
            "sketch",
            "painting",
            "collage",
            "visual",
            "diagram",
            "infographic",
            "chart",
            "map",
            "QR code",
            "JPEG",
            "JPG",
            "PNG",
            "GIF",
            "WebP",
            "SVG",
        )

        for term in terms:
            with self.subTest(term=term):
                fields = self.agent.resolve(f"Place a {term} in the top half.")
                self.assertIn("image_url", {field.name for field in fields})

    def test_plural_visual_terms_request_an_image_url(self) -> None:
        for term in ("images", "photos", "pictures", "pics", "logos", "portraits"):
            with self.subTest(term=term):
                fields = self.agent.resolve(f"Add two {term} to the page.")
                self.assertIn("image_url", {field.name for field in fields})

    def test_picture_does_not_match_inside_an_unrelated_word(self) -> None:
        fields = self.agent.resolve("Write about a picturesque town.")
        self.assertNotIn("image_url", {field.name for field in fields})

    def test_pic_does_not_match_inside_an_unrelated_word(self) -> None:
        fields = self.agent.resolve("Write an article about a topic.")
        self.assertNotIn("image_url", {field.name for field in fields})

    def test_hero_picture_uses_specific_hero_field(self) -> None:
        fields = self.agent.resolve("Add a hero picture across the top.")
        names = {field.name for field in fields}
        self.assertIn("hero_image_url", names)
        self.assertNotIn("image_url", names)

    def test_guest_writer_portrait_uses_specific_guest_writer_field(self) -> None:
        fields = self.agent.resolve("Add a portrait of the guest writer.")
        names = {field.name for field in fields}
        self.assertIn("guest_writer_photo_url", names)
        self.assertNotIn("image_url", names)

    def test_optional_template_image_only_blocks_when_requested(self) -> None:
        template = {
            "requiredFields": [
                {
                    "name": "hero_image_url",
                    "question": "Hero image URL",
                    "type": "image",
                    "required": False,
                }
            ]
        }
        normal = {field.name: field for field in self.agent.resolve("Write an article", template)}
        requested = {
            field.name: field
            for field in self.agent.resolve("Write an article with an image", template)
        }
        spread = {
            field.name: field
            for field in self.agent.resolve("Use a two page image spread", template)
        }
        self.assertFalse(normal["hero_image_url"].required)
        self.assertTrue(requested["hero_image_url"].required)
        self.assertFalse(spread["hero_image_url"].required)
        self.assertTrue(spread["spread_image_url"].required)

    def test_prompt_mention_upgrades_optional_field_to_required(self) -> None:
        fields = {
            field.name: field
            for field in self.agent.resolve("Include the publisher and publication date")
        }
        self.assertTrue(fields["publisher_name"].required)
        self.assertTrue(fields["publication_date"].required)

    def test_cli_skips_unrequested_optional_fields(self) -> None:
        prompts: list[str] = []
        collected = InformationAgent(
            input_fn=lambda prompt: prompts.append(prompt) or "required value",
            output_fn=lambda _message: None,
        ).collect(
            [
                RequiredField("title", "Title"),
                RequiredField("hero_image_url", "Hero", "image", required=False),
            ]
        )
        self.assertEqual(collected, {"title": "required value"})
        self.assertEqual(len(prompts), 1)


if __name__ == "__main__":
    unittest.main()
