import json
from datetime import datetime
from pathlib import Path

from core.config import OUTPUTS_DIR


class RunRecorder:
    """
    Stores full pipeline execution trace for debugging + evaluation.
    """

    def __init__(self):
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_path = OUTPUTS_DIR / f"runs/run_{timestamp}.json"

        self.data = {
            "timestamp": timestamp,
            "user_prompt": None,
            "retrieval_candidates": [],
            "reranked_candidates": [],
            "final_context": [],
            "generation_response": None,
            "validation_status": None,
        }

    def set_prompt(self, prompt: str):
        self.data["user_prompt"] = prompt

    def set_retrieval(self, candidates: list):
        self.data["retrieval_candidates"] = candidates

    def set_reranked(self, candidates: list):
        self.data["reranked_candidates"] = candidates

    def set_context(self, context: list):
        self.data["final_context"] = context

    def set_generation(self, response: str):
        self.data["generation_response"] = response

    def set_validation_status(self, status: str):
        self.data["validation_status"] = status

    def save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

        return self.file_path
