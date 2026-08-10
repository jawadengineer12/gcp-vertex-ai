import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from streamlit_app import _show_result, api_request


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return b'{"templates":[{"id":"article","name":"Article"}]}'


class ApiRequestTests(unittest.TestCase):
    @patch("streamlit_app.urlopen", return_value=FakeResponse())
    def test_successful_json_request(self, mocked_urlopen) -> None:
        status, body = api_request("http://localhost:8080", "secret", "/v1/templates")

        self.assertEqual(status, 200)
        self.assertEqual(body["templates"][0]["id"], "article")
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.get_header("X-api-key"), "secret")

    @patch("streamlit_app.urlopen")
    def test_structured_http_error_is_preserved(self, mocked_urlopen) -> None:
        mocked_urlopen.side_effect = HTTPError(
            "http://localhost:8080/v1/layouts",
            502,
            "Bad Gateway",
            {},
            io.BytesIO(b'{"status":"publish_failed","layout":{"pages":[]}}'),
        )

        status, body = api_request(
            "http://localhost:8080",
            "secret",
            "/v1/layouts",
            {"publish": True},
        )

        self.assertEqual(status, 502)
        self.assertEqual(body["status"], "publish_failed")
        self.assertIn("layout", body)


class ResultDisplayTests(unittest.TestCase):
    @patch("streamlit_app.st")
    def test_complete_publisher_response_is_shown_when_body_is_empty(self, streamlit) -> None:
        publisher = {"status_code": 200, "body": ""}

        _show_result(
            {
                "status": "completed",
                "request_id": "req_demo",
                "publisher": publisher,
                "timing_ms": {},
                "layout": {"pages": []},
            }
        )

        streamlit.expander.assert_called_once_with("Publishing response")
        streamlit.json.assert_any_call(publisher, expanded=True)


if __name__ == "__main__":
    unittest.main()
