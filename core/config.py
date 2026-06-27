import os
from pathlib import Path

# --- BASE PATHS ---
BASE_DIR = Path(__file__).resolve().parent.parent
NORMALIZED_DATA_DIR = BASE_DIR / "normalized_data"
RAW_DATA_DIR = BASE_DIR / "raw_data"
OUTPUTS_DIR = BASE_DIR / "outputs"
LOGS_DIR = BASE_DIR / "logs"
VECTOR_DATA_PATH = NORMALIZED_DATA_DIR / "vertex_index_data.jsonl"

# --- FILE PATHS ---
LIBRARY_PATH = NORMALIZED_DATA_DIR / "layout_prompt_library.json"
UPDATED_LIBRARY_PATH = NORMALIZED_DATA_DIR / "layout_prompt_library_updated.json"
EXCEL_FILE_PATH = RAW_DATA_DIR / "trainingData_Local.xlsx"
RAW_TEXT_DATA_PATH = RAW_DATA_DIR / "LAS 4_V8_links_data with Descriptions.txt"
VERTEX_INDEX_PATH = NORMALIZED_DATA_DIR / "vertex_index_data.jsonl"
GENERATED_LAYOUT_PATH = OUTPUTS_DIR / "generated_layout.json"
PIPELINE_LOG_PATH = LOGS_DIR / "pipeline.log"

# --- GCP VERTEX AI SETTINGS ---
VERTEX_PROJECT = os.getenv("VERTEX_PROJECT_ID", "indesign-layout-ai")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
GENERATION_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "text-embedding-004"

# --- PIPELINE THRESHOLDS ---
STAGE_1_TOP_K = 10
FINAL_TOP_K = 5
MAX_RETRIES = 3
WEIGHT_VECTOR = 0.7
WEIGHT_BM25 = 0.3
EMBEDDING_BATCH_SIZE = 100

# --- GENERATION SETTINGS ---
GENERATION_TEMPERATURE = 0.2

# --- RERANKER SETTINGS ---
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# --- LOGGING SETTINGS ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_MAX_BYTES = 5_000_000
LOG_BACKUP_COUNT = 5
