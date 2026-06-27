# services/trace_service.py
"""
Run trace writer.
Writes a structured JSON trace of every pipeline run to outputs/run_traces/.
Controlled by ENABLE_RUN_TRACE in .env.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from config.config import AppConfig

logger = logging.getLogger(__name__)


def write_trace(trace: dict) -> Path | None:
    """
    Writes the run trace dict to a timestamped JSON file.
    Returns the path written, or None if tracing is disabled.
    """
    if not AppConfig.ENABLE_RUN_TRACE:
        return None

    trace_dir = AppConfig.RUN_TRACE_DIR
    trace_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_path = trace_dir / f"run_{timestamp}.json"

    try:
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2, default=str)
        logger.info("Run trace saved: %s", trace_path)
    except Exception as e:
        logger.warning("Failed to write run trace: %s", str(e))
        return None

    return trace_path


def build_trace(
    user_prompt: str,
    vector_candidates: list,
    bm25_candidates: list,
    merged_candidates: list,
    reranked_candidates: list,
    selected_context: list,
    gemini_raw_response: str,
    parsed_json: dict | None,
    validation_success: bool,
    validation_errors: list[str],
    output_file: str,
) -> dict:
    """Assembles the full trace dict."""
    return {
        "user_prompt": user_prompt,
        "vector_candidates": _slim(vector_candidates),
        "bm25_candidates": _slim(bm25_candidates),
        "merged_candidates": _slim(merged_candidates),
        "reranked_candidates": _slim(reranked_candidates),
        "selected_context": _slim(selected_context),
        "gemini_raw_response": gemini_raw_response or "",
        "parsed_json": parsed_json or {},
        "validation": {
            "success": validation_success,
            "errors": validation_errors,
        },
        "output_file": output_file,
    }


def _slim(candidates: list) -> list:
    """
    Strips large expected_layout_json blobs from trace entries to keep
    trace files readable. Keeps scores and metadata.
    """
    slim = []
    for c in candidates:
        slim.append({
            "id": c.get("id"),
            "pageIndex": c.get("pageIndex"),
            "natural_language_intent": c.get("natural_language_intent", "")[:200],
            "vector_score": round(c.get("vector_score", 0.0), 4),
            "bm25_score": round(c.get("bm25_score", 0.0), 4),
            "final_score": round(c.get("final_score", 0.0), 4),
            "rerank_score": round(c.get("rerank_score", 0.0), 4) if "rerank_score" in c else None,
        })
    return slim
