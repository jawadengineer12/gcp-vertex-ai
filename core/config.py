"""Single tracked configuration source for the layout pipeline."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Tests that only use local services do not require dotenv.
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _bool(key: str, default: str) -> bool:
    return _get(key, default).strip().casefold() in {"1", "true", "yes", "on"}


def _path(key: str, default: str) -> Path:
    value = Path(_get(key, default)).expanduser()
    return value if value.is_absolute() else BASE_DIR / value


class AppConfig:
    PROJECT_ID = _get("GOOGLE_CLOUD_PROJECT")
    LOCATION = _get("GOOGLE_CLOUD_LOCATION", "us-central1")
    GCS_VECTOR_BUCKET_URI = _get("GCS_VECTOR_BUCKET_URI")

    PROMPT_LIBRARY_PATH = _path(
        "PROMPT_LIBRARY_PATH", "normalized_data/layout_prompt_library_updated.json"
    )
    RAW_TEXT_DATA_PATH = _path(
        "RAW_TEXT_DATA_PATH", "raw_data/LAS 4_V8_links_data with Descriptions.txt"
    )
    EXCEL_FILE_PATH = _path("EXCEL_FILE_PATH", "raw_data/trainingData_Local.xlsx")
    VERTEX_INDEX_DATA_PATH = _path(
        "VERTEX_INDEX_DATA_PATH", "normalized_data/vertex_index_data.json"
    )
    OUTPUT_FILE = _path("OUTPUT_FILE", "outputs/generated_layout.json")
    RUN_TRACE_DIR = _path("RUN_TRACE_DIR", "outputs/run_traces")
    TEMPLATE_DIR = _path("TEMPLATE_DIR", "templates")
    FONT_LIST_PATH = _path("FONT_LIST_PATH", "raw_data/Font List.csv")

    LOCAL_OUTPUT = _bool("LOCAL_OUTPUT", "true")
    GCS_BUCKET = _get("GCS_BUCKET")
    GCS_OBJECT_NAME = _get("GCS_OBJECT_NAME") or None
    PUBLISHER_API_URL = _get("PUBLISHER_API_URL")
    PUBLISHER_API_KEY = _get("PUBLISHER_API_KEY")
    PUBLISHER_CREATED_BY = _get("PUBLISHER_CREATED_BY", "test_user@bubble.com")
    PUBLISHER_PROJECT = _get("PUBLISHER_PROJECT", "Heroku Integration Test")
    LAYOUT_API_KEY = _get("LAYOUT_API_KEY")
    LAYOUT_API_URL = _get("LAYOUT_API_URL", "http://localhost:8080")

    LOG_DIR = _path("LOG_DIR", "logs")
    LOG_LEVEL = _get("LOG_LEVEL", "INFO")
    LOG_MAX_BYTES = int(_get("LOG_MAX_BYTES", "10485760"))
    LOG_BACKUP_COUNT = int(_get("LOG_BACKUP_COUNT", "3"))
    PIPELINE_LOG_PATH = LOG_DIR / "pipeline.log"
    ENABLE_RUN_TRACE = _bool("ENABLE_RUN_TRACE", "true")

    EMBEDDING_MODEL = _get("EMBEDDING_MODEL", "text-embedding-004")
    GENERATION_MODEL = _get("GENERATION_MODEL", "gemini-2.5-flash")
    RERANKER_MODEL_NAME = _get(
        "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    GEMINI_TEMPERATURE = float(_get("GEMINI_TEMPERATURE", "0.2"))
    VECTOR_WEIGHT = float(_get("VECTOR_WEIGHT", "0.7"))
    BM25_WEIGHT = float(_get("BM25_WEIGHT", "0.3"))
    TOP_K_VECTOR = int(_get("TOP_K_VECTOR", "10"))
    TOP_K_BM25 = int(_get("TOP_K_BM25", "10"))
    TOP_K_MERGED = int(_get("TOP_K_MERGED", "10"))
    TOP_K_RERANKED = int(_get("TOP_K_RERANKED", "5"))
    TOP_K_CONTEXT = int(_get("TOP_K_CONTEXT", "2"))
    MAX_RETRIES = int(_get("MAX_RETRIES", "3"))

    SAFE_MARGIN = float(_get("SAFE_MARGIN", "0.25"))
    IMAGE_BLEED = float(_get("IMAGE_BLEED", "0.125"))
    AD_BOUNDARY_TOLERANCE = float(_get("AD_BOUNDARY_TOLERANCE", "0.5"))

    @classmethod
    def validate_vertex_config(cls) -> None:
        missing = [
            key
            for key, value in {
                "GOOGLE_CLOUD_PROJECT": cls.PROJECT_ID,
            }.items()
            if not value
        ]
        if missing:
            raise EnvironmentError(
                "Missing Vertex configuration: " + ", ".join(missing)
            )


# Compatibility aliases used by existing utility scripts.
OUTPUTS_DIR = BASE_DIR / "outputs"
LIBRARY_PATH = AppConfig.PROMPT_LIBRARY_PATH
UPDATED_LIBRARY_PATH = AppConfig.PROMPT_LIBRARY_PATH
RAW_TEXT_DATA_PATH = AppConfig.RAW_TEXT_DATA_PATH
EXCEL_FILE_PATH = AppConfig.EXCEL_FILE_PATH
VERTEX_INDEX_PATH = AppConfig.VERTEX_INDEX_DATA_PATH
EMBEDDING_MODEL = AppConfig.EMBEDDING_MODEL
STAGE_1_TOP_K = AppConfig.TOP_K_MERGED
PIPELINE_LOG_PATH = AppConfig.PIPELINE_LOG_PATH
LOG_LEVEL = AppConfig.LOG_LEVEL
LOG_MAX_BYTES = AppConfig.LOG_MAX_BYTES
LOG_BACKUP_COUNT = AppConfig.LOG_BACKUP_COUNT
