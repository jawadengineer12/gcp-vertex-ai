import unittest

from services.requirement_agent import RequirementAgent


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


if __name__ == "__main__":
    unittest.main()
