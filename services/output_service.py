"""LayoutProject persistence and optional publisher submission."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class OutputService:
    def __init__(
        self,
        output_file: Path,
        local_output: bool = True,
        gcs_bucket: str = "",
        gcs_object_name: str | None = None,
        publisher_url: str = "",
        publisher_api_key: str = "",
        publisher_created_by: str = "test_user@bubble.com",
        publisher_project: str = "Heroku Integration Test",
    ) -> None:
        if not local_output and not gcs_bucket and not publisher_url:
            raise ValueError("Enable LOCAL_OUTPUT, configure GCS_BUCKET, or configure publishing")
        self.output_file = output_file
        self.local_output = local_output
        self.gcs_bucket = gcs_bucket.removeprefix("gs://").rstrip("/")
        self.gcs_object_name = gcs_object_name or output_file.name
        if publisher_url or publisher_api_key:
            self.validate_publisher_config(publisher_url, publisher_api_key)
        self.publisher_url = publisher_url
        self.publisher_api_key = publisher_api_key
        self.publisher_created_by = publisher_created_by
        self.publisher_project = publisher_project

    def save_json(self, payload: dict) -> dict[str, str]:
        serialized = json.dumps(payload, indent=2, ensure_ascii=False)
        destinations: dict[str, str] = {}
        if self.local_output:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            self.output_file.write_text(serialized + "\n", encoding="utf-8")
            destinations["local"] = str(self.output_file)
        if self.gcs_bucket:
            try:
                from google.cloud import storage
            except ImportError as error:
                raise RuntimeError(
                    "GCS output requires the google-cloud-storage package"
                ) from error
            client = storage.Client()
            blob = client.bucket(self.gcs_bucket).blob(self.gcs_object_name)
            blob.upload_from_string(serialized, content_type="application/json")
            destinations["gcs"] = f"gs://{self.gcs_bucket}/{self.gcs_object_name}"
        return destinations

    def queue_job(self, payload: dict) -> tuple[int, str] | None:
        if not self.publisher_url:
            return None

        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
        envelope = {
            "_id": f"test_{time.time_ns() // 1_000_000}",
            "Created By": self.publisher_created_by,
            "Project": self.publisher_project,
            "Created Date": timestamp,
            "Modified Date": timestamp,
            "Prompt": "var documentData="
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        }
        request = Request(
            self.publisher_url,
            data=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.publisher_api_key,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                return response.status, response.read().decode("utf-8", errors="replace")
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace") or str(error.reason)
            raise RuntimeError(
                f"Publisher queue rejected request ({error.code}): {detail}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise RuntimeError(f"Publisher queue request failed: {error}") from error

    @staticmethod
    def validate_publisher_config(url: str, api_key: str) -> None:
        if not url or not api_key:
            raise ValueError("Configure both PUBLISHER_API_URL and PUBLISHER_API_KEY")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("PUBLISHER_API_URL must use HTTPS")
