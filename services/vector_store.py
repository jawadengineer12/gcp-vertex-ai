"""Exact in-process vector lookup for the small prompt library."""

import json
import logging
from pathlib import Path

import numpy as np

from core.config import AppConfig

logger = logging.getLogger(__name__)


class LocalVectorStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or AppConfig.VERTEX_INDEX_DATA_PATH
        records = [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        if not records:
            raise ValueError(f"Vector data is empty: {self.path}")

        self.ids = [record["id"] for record in records]
        if len(self.ids) != len(set(self.ids)):
            raise ValueError(f"Vector data contains duplicate IDs: {self.path}")

        self.embeddings = np.asarray(
            [record["embedding"] for record in records], dtype=np.float32
        )
        if self.embeddings.ndim != 2 or not np.isfinite(self.embeddings).all():
            raise ValueError(
                f"Vector data must be a finite two-dimensional matrix: {self.path}"
            )

        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise ValueError(
                f"Vector data contains a zero-length embedding: {self.path}"
            )
        self.embeddings /= norms
        logger.info(
            "LocalVectorStore initialized | records=%d | dimensions=%d",
            len(self.ids),
            self.embeddings.shape[1],
        )

    def find_nearest_neighbors(
        self, query_embedding: list[float], k: int = 10
    ) -> list[str]:
        query = np.asarray(query_embedding, dtype=np.float32)
        if query.ndim != 1 or query.shape[0] != self.embeddings.shape[1]:
            raise ValueError(
                f"Query embedding has {query.size} dimensions; "
                f"expected {self.embeddings.shape[1]}"
            )
        if not np.isfinite(query).all() or np.linalg.norm(query) == 0:
            raise ValueError("Query embedding must contain finite, non-zero values")

        scores = self.embeddings @ (query / np.linalg.norm(query))
        limit = min(max(k, 0), len(self.ids))
        order = np.argsort(-scores, kind="stable")[:limit]
        return [self.ids[index] for index in order]
