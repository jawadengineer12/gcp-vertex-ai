import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError

from pydantic import ValidationError

from schemas.layout_schema import LayoutProject
from services.font_service import load_allowed_fonts
from services.output_service import OutputService
from services.retrieval_service import RetrievalService
from services.validation_service import ValidationService
from services.vector_store import LocalVectorStore


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
                    "content": {"textBody": "An article about cats."},
                    "columns": 1,
                    "gutterSize": 0.2,
                    "margins": {
                        "top": 0.0,
                        "left": 0.0,
                        "bottom": 0.0,
                        "right": 0.0,
                    },
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


class FakeResponse:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return b'{"jobId":"demo-1"}'


class LayoutContractTests(unittest.TestCase):
    def test_converter_article_shape(self) -> None:
        LayoutProject.model_validate(VALID_LAYOUT)
        ValidationService(["Adobe Garamond Pro\\tRegular"]).validate_payload(
            VALID_LAYOUT
        )

        nested = deepcopy(VALID_LAYOUT)
        article = nested["pages"][0]["assets"][0]
        for field in ("columns", "gutterSize", "margins", "textStyle"):
            article["content"][field] = article.pop(field)
        with self.assertRaises(ValidationError):
            LayoutProject.model_validate(nested)

    def test_adobe_garamond_exact_names_come_from_column_c(self) -> None:
        fonts = load_allowed_fonts(
            Path(__file__).parents[1] / "raw_data" / "Font List.csv"
        )
        self.assertTrue(
            {
                "Adobe Garamond Pro\\tRegular",
                "Adobe Garamond Pro\\tItalic",
                "Adobe Garamond Pro\\tSemibold",
                "Adobe Garamond Pro\\tBold",
            }.issubset(fonts)
        )


class LocalVectorStoreTests(unittest.TestCase):
    def test_exact_cosine_ranking_and_dimension_validation(self) -> None:
        records = [
            {"id": "x", "embedding": [1.0, 0.0]},
            {"id": "y", "embedding": [0.0, 1.0]},
            {"id": "diagonal", "embedding": [1.0, 1.0]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vectors.json"
            path.write_text(
                "\n".join(json.dumps(record) for record in records),
                encoding="utf-8",
            )
            store = LocalVectorStore(path)

            self.assertEqual(
                store.find_nearest_neighbors([0.9, 0.1], k=2),
                ["x", "diagonal"],
            )
            with self.assertRaisesRegex(ValueError, "expected 2"):
                store.find_nearest_neighbors([1.0], k=1)

    def test_packaged_vectors_match_prompt_library(self) -> None:
        root = Path(__file__).parents[1]
        library = json.loads(
            (root / "normalized_data" / "layout_prompt_library_updated.json").read_text(
                encoding="utf-8"
            )
        )
        records = [
            json.loads(line)
            for line in (
                root / "normalized_data" / "vertex_index_data.json"
            ).read_text(encoding="utf-8").splitlines()
            if line
        ]

        self.assertEqual(
            {record["id"] for record in records},
            {item["id"] for item in library},
        )
        self.assertEqual({len(record["embedding"]) for record in records}, {768})
        store = LocalVectorStore(
            root / "normalized_data" / "vertex_index_data.json"
        )
        for record in records:
            self.assertEqual(
                store.find_nearest_neighbors(record["embedding"], k=1),
                [record["id"]],
            )

    @patch("services.retrieval_service.get_vertex_client")
    def test_retrieval_pipeline_uses_packaged_vectors(self, client_factory) -> None:
        root = Path(__file__).parents[1]
        first_record = json.loads(
            (root / "normalized_data" / "vertex_index_data.json")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        client_factory.return_value.models.embed_content.return_value = SimpleNamespace(
            embeddings=[SimpleNamespace(values=first_record["embedding"])]
        )

        result = RetrievalService().execute_pipeline("local vector integration test")

        self.assertEqual(result["vector_candidates"][0]["id"], first_record["id"])


class PublisherSubmissionTests(unittest.TestCase):
    def make_output(self, path: Path) -> OutputService:
        return OutputService(
            output_file=path,
            publisher_url="https://publisher.example/api/bubble/queue-job",
            publisher_api_key="rotated-test-key",
            publisher_created_by="demo@example.com",
            publisher_project="AI Demo",
        )

    @patch("services.output_service.urlopen", return_value=FakeResponse())
    def test_saves_json_then_queues_wrapped_prompt(self, mocked_urlopen) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            output = self.make_output(path)
            output.save_json(VALID_LAYOUT)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), VALID_LAYOUT)

            self.assertEqual(output.queue_job(VALID_LAYOUT), (202, '{"jobId":"demo-1"}'))
            request = mocked_urlopen.call_args.args[0]
            envelope = json.loads(request.data.decode("utf-8"))

            self.assertEqual(request.method, "POST")
            self.assertEqual(request.get_header("Content-type"), "application/json")
            self.assertEqual(request.get_header("X-api-key"), "rotated-test-key")
            self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 30)
            self.assertTrue(envelope["_id"].startswith("test_"))
            self.assertEqual(envelope["Created Date"], envelope["Modified Date"])
            self.assertTrue(envelope["Prompt"].startswith("var documentData="))
            self.assertFalse(envelope["Prompt"].endswith(";"))
            self.assertEqual(
                json.loads(envelope["Prompt"].removeprefix("var documentData=")),
                VALID_LAYOUT,
            )

    @patch("services.output_service.urlopen", side_effect=URLError("offline"))
    def test_submission_failure_preserves_saved_json(self, _mocked_urlopen) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            output = self.make_output(path)
            output.save_json(VALID_LAYOUT)

            with self.assertRaisesRegex(RuntimeError, "offline"):
                output.queue_job(VALID_LAYOUT)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), VALID_LAYOUT)

    def test_rejects_insecure_or_partial_publisher_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            with self.assertRaisesRegex(ValueError, "both"):
                OutputService(output_file=path, publisher_url="https://publisher.example")
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                OutputService(
                    output_file=path,
                    publisher_url="http://publisher.example",
                    publisher_api_key="key",
                )


if __name__ == "__main__":
    unittest.main()
