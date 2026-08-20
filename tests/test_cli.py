import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import main as cli
from main import _publisher_settings


class CliPublishSafetyTests(unittest.TestCase):
    @patch("main.AppConfig.PUBLISHER_API_KEY", "configured-key")
    @patch("main.AppConfig.PUBLISHER_API_URL", "https://publisher.example/queue")
    def test_publishing_is_disabled_without_flag(self) -> None:
        self.assertEqual(_publisher_settings(False), ("", ""))

    @patch("main.AppConfig.PUBLISHER_API_KEY", "configured-key")
    @patch("main.AppConfig.PUBLISHER_API_URL", "https://publisher.example/queue")
    def test_publish_flag_uses_configured_endpoint(self) -> None:
        self.assertEqual(
            _publisher_settings(True),
            ("https://publisher.example/queue", "configured-key"),
        )

    @patch("main.AppConfig.PUBLISHER_API_KEY", "")
    @patch("main.AppConfig.PUBLISHER_API_URL", "")
    def test_publish_flag_requires_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "--publish requires"):
            _publisher_settings(True)

    @patch("main.AppConfig.PUBLISHER_API_KEY", "")
    @patch("main.AppConfig.PUBLISHER_API_URL", "")
    @patch("main.setup_logging")
    def test_missing_publish_configuration_fails_before_generation(
        self, setup_logging
    ) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            cli.main(["--publish"])
        self.assertEqual(raised.exception.code, 2)
        setup_logging.assert_not_called()


if __name__ == "__main__":
    unittest.main()
