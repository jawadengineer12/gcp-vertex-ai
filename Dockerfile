FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENABLE_RUN_TRACE=false \
    LOCAL_OUTPUT=false \
    HF_HOME=/opt/huggingface \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --no-install-project

ARG RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
ENV RERANKER_MODEL=$RERANKER_MODEL
RUN python -c "import os; from sentence_transformers import CrossEncoder; CrossEncoder(os.environ['RERANKER_MODEL'])"

COPY . .

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
