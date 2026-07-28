# Vertex AI Layout RAG

Python pipeline that retrieves relevant layout examples with Vertex AI Vector
Search, generates structured layout JSON with Gemini, and validates the result
against strict converter-facing layout rules.

## Requirements

- Python 3.12 or newer
- A Google Cloud project with Vertex AI and Cloud Storage enabled
- A deployed Vertex AI Vector Search index

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
```

Fill in the Google Cloud and Vector Search values in `.env`. Never commit that
file or a service-account key.

For the complete Google Cloud setup, vector-data import, index creation, and
endpoint deployment workflow, see [GCP_SETUP.md](GCP_SETUP.md).

## Run

```powershell
python main.py
```

The validated layout is written under `outputs/`, and optional execution traces
are written under `outputs/run_traces/`. Both locations are intentionally
excluded from Git.

## Refresh vector data

```powershell
python -m scripts.prepare_vertex_vector_data
gcloud.cmd storage cp normalized_data/vertex_index_data.json `
  gs://YOUR_VECTOR_BUCKET/
```

The generated file contains one JSON vector record per line but deliberately
uses the `.json` extension required by Vertex AI batch import.
