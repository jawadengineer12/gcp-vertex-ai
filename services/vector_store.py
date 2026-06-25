import json
from pathlib import Path
from core.config import VECTOR_DATA_PATH

def load_vector_store():
    with open(VECTOR_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)