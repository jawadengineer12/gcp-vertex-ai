"""Local and optional GCS LayoutProject persistence."""

import json
from pathlib import Path


class OutputService:
    def __init__(
        self,
        output_file: Path,
        local_output: bool = True,
        gcs_bucket: str = "",
        gcs_object_name: str | None = None,
    ) -> None:
        if not local_output and not gcs_bucket:
            raise ValueError("Enable LOCAL_OUTPUT or configure GCS_BUCKET")
        self.output_file = output_file
        self.local_output = local_output
        self.gcs_bucket = gcs_bucket.removeprefix("gs://").rstrip("/")
        self.gcs_object_name = gcs_object_name or output_file.name

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
