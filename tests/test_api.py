import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import api


VALID_LAYOUT = {
    "pageIndex": 0,
    "documentSettings": {"pageWidth": 8.5, "pageHeight": 11.0},
    "projectInfo": {"projectName": "Cat Article"},
    "pages": [
        {
            "pageIndex": 1,
            "assets": [
                {
                    "assetType": "Article",
                    "position": {"startX": 0.25, "startY": 0.25},
                    "size": {"width": 3.5, "height": 5.0},
                    "content": {"textBody": "Cats."},
                    "columns": 1,
                    "gutterSize": 0.2,
                    "margins": {"top": 0.0, "left": 0.0, "bottom": 0.0, "right": 0.0},
                    "textStyle": {
                        "fontFamily": "Adobe Garamond Pro\\tRegular",
                        "fontSize": 10.0,
                        "bold": False,
                        "italic": False,
                        "underline": False,
                        "color": "#000000",
                        "autoFit": True,
                    },
                }
            ],
        }
    ],
}


def completed_result() -> SimpleNamespace:
    return SimpleNamespace(
        layout=deepcopy(VALID_LAYOUT),
        timing_ms={
            "retrieval": 1,
            "reranking": 2,
            "generation": 3,
            "validation": 4,
            "total": 10,
        },
        retries=0,
        retrieval_result={
            "vector_candidates": [],
            "bm25_candidates": [],
            "merged_candidates": [],
        },
        reranked_candidates=[],
        selected_context=[],
        raw_response="{}",
        validation_errors=[],
    )


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_layout_key = api.AppConfig.LAYOUT_API_KEY
        self.old_publisher_url = api.AppConfig.PUBLISHER_API_URL
        self.old_publisher_key = api.AppConfig.PUBLISHER_API_KEY
        api.AppConfig.LAYOUT_API_KEY = "layout-test-key"
        api.AppConfig.PUBLISHER_API_URL = "https://publisher.example/queue"
        api.AppConfig.PUBLISHER_API_KEY = "publisher-test-key"
        self.client = TestClient(api.app)
        self.headers = {"x-api-key": "layout-test-key"}

    def tearDown(self) -> None:
        api.AppConfig.LAYOUT_API_KEY = self.old_layout_key
        api.AppConfig.PUBLISHER_API_URL = self.old_publisher_url
        api.AppConfig.PUBLISHER_API_KEY = self.old_publisher_key

    def request(self, **overrides):
        payload = {
            "request_id": None,
            "prompt": "Create a cat article with an image",
            "template_id": "magazine_article",
            "answers": {},
            "publish": False,
        }
        payload.update(overrides)
        return self.client.post("/v1/layouts", headers=self.headers, json=payload)

    def test_health_is_public_and_templates_require_auth(self) -> None:
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/v1/templates").status_code, 401)
        response = self.client.get("/v1/templates", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["templates"][0]["id"], "magazine_article")
        self.assertEqual(response.json()["templates"][0]["fields"][0]["type"], "text")

    @patch("api.get_pipeline_service", side_effect=AssertionError("paid service loaded"))
    def test_missing_fields_do_not_load_pipeline(self, _pipeline) -> None:
        response = self.request()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "needs_input")
        self.assertTrue(body["request_id"].startswith("req_"))
        self.assertEqual(
            [field["name"] for field in body["missing_fields"]],
            ["article_title", "author_name", "hero_image_url"],
        )

    @patch("api.get_pipeline_service")
    def test_prompt_values_and_https_url_are_extracted(self, pipeline_factory) -> None:
        pipeline_factory.return_value.generate.return_value = completed_result()
        response = self.request(
            prompt=(
                "Create an article; article_title: Cat Life; author_name: Jane Doe; "
                "hero_image_url: https://images.example/cat.jpg"
            )
        )
        self.assertEqual(response.status_code, 200)
        known = pipeline_factory.return_value.generate.call_args.args[1]
        self.assertEqual(known["article_title"], "Cat Life")
        self.assertEqual(known["author_name"], "Jane Doe")
        self.assertEqual(known["hero_image_url"], "https://images.example/cat.jpg")

    @patch("api.get_pipeline_service")
    def test_resubmission_answers_override_prompt_and_null_uses_placeholder(
        self, pipeline_factory
    ) -> None:
        pipeline_factory.return_value.generate.return_value = completed_result()
        response = self.request(
            request_id="req_client_1",
            prompt="article_title: Old title; author_name: Old Author",
            answers={
                "article_title": "New title",
                "author_name": "New Author",
                "hero_image_url": None,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["request_id"], "req_client_1")
        known = pipeline_factory.return_value.generate.call_args.args[1]
        self.assertEqual(known["article_title"], "New title")
        self.assertEqual(known["author_name"], "New Author")
        self.assertEqual(known["hero_image_url"], "[hero_image_url]")

    def test_auth_and_invalid_inputs_return_422_or_401(self) -> None:
        self.assertEqual(self.client.post("/v1/layouts", json={}).status_code, 401)
        self.assertEqual(self.request(prompt="").status_code, 422)
        self.assertEqual(self.request(prompt="x" * 10_001).status_code, 422)
        self.assertEqual(self.request(template_id="missing").status_code, 422)
        self.assertEqual(self.request(answers={"unknown": "value"}).status_code, 422)
        self.assertEqual(
            self.request(
                answers={
                    "article_title": "Cats",
                    "author_name": "Jane Doe",
                    "hero_image_url": "http://images.example/cat.jpg",
                }
            ).status_code,
            422,
        )

    @patch("api.OutputService.queue_job", side_effect=AssertionError("publisher called"))
    @patch("api.get_pipeline_service")
    def test_publish_false_never_contacts_publisher(self, pipeline_factory, _queue) -> None:
        pipeline_factory.return_value.generate.return_value = completed_result()
        response = self.request(
            answers={
                "article_title": "Cats",
                "author_name": "Jane Doe",
                "hero_image_url": None,
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["publisher"])

    @patch("api.OutputService.queue_job", return_value=(202, '{"job":"1"}'))
    @patch("api.get_pipeline_service")
    def test_publish_true_submits_validated_layout(self, pipeline_factory, queue) -> None:
        pipeline_factory.return_value.generate.return_value = completed_result()
        response = self.request(
            publish=True,
            answers={
                "article_title": "Cats",
                "author_name": "Jane Doe",
                "hero_image_url": None,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["publisher"]["status_code"], 202)
        self.assertEqual(queue.call_args.args[0], VALID_LAYOUT)

    @patch("api.OutputService.queue_job", side_effect=RuntimeError("offline"))
    @patch("api.get_pipeline_service")
    def test_publisher_failure_returns_generated_layout(self, pipeline_factory, _queue) -> None:
        pipeline_factory.return_value.generate.return_value = completed_result()
        response = self.request(
            publish=True,
            answers={
                "article_title": "Cats",
                "author_name": "Jane Doe",
                "hero_image_url": None,
            },
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["status"], "publish_failed")
        self.assertEqual(response.json()["layout"], VALID_LAYOUT)

    @patch("api.get_pipeline_service", side_effect=AssertionError("pipeline loaded"))
    def test_publish_config_is_checked_before_generation(self, _pipeline) -> None:
        api.AppConfig.PUBLISHER_API_KEY = ""
        response = self.request(
            publish=True,
            answers={
                "article_title": "Cats",
                "author_name": "Jane Doe",
                "hero_image_url": None,
            },
        )
        self.assertEqual(response.status_code, 503)

    def test_pipeline_service_is_cached(self) -> None:
        from services.pipeline_service import get_pipeline_service

        get_pipeline_service.cache_clear()
        self.assertIs(api.get_pipeline_service(), api.get_pipeline_service())


if __name__ == "__main__":
    unittest.main()
