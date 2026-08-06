# Vertex AI Layout RAG

Python pipeline that retrieves relevant layout examples with exact local vector
search plus BM25, generates structured layout JSON with Gemini, and validates
the result against strict converter-facing layout rules.

## Requirements

- Python 3.12 or newer
- A Google Cloud project with Vertex AI enabled
- The checked-in local embedding file under `normalized_data/`

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
```

Fill in the Google Cloud project and location in `.env`. Never commit that file
or a service-account key.

For the complete Google Cloud and Cloud Run setup, see
[GCP_SETUP.md](GCP_SETUP.md).

## Run

```powershell
python main.py
```

The validated layout is written under `outputs/`, and optional execution traces
are written under `outputs/run_traces/`. Both locations are intentionally
excluded from Git.

## Hosted test API

Set a dedicated inbound key and start one Uvicorn worker:

```powershell
$env:LAYOUT_API_KEY="replace-with-a-long-random-key"
$env:ENABLE_RUN_TRACE="false"
uv run uvicorn api:app --host 0.0.0.0 --port 8080 --workers 1
```

`GET /health` is public on Cloud Run; `/healthz` remains available locally but
Cloud Run reserves some paths ending in `z`. Send `x-api-key` to `GET /v1/templates` and
`POST /v1/layouts`. The layout endpoint is stateless: resend the same prompt,
the returned `request_id`, and accumulated answers until `status` is
`completed`. A JSON `null` answer accepts that field's standard placeholder;
omitting an answer leaves it unresolved.

```powershell
$headers = @{ "x-api-key" = $env:LAYOUT_API_KEY }
$body = @{
  request_id = $null
  prompt = "Create a cat article with an image"
  template_id = "magazine_article"
  answers = @{}
  publish = $false
} | ConvertTo-Json
Invoke-RestMethod http://localhost:8080/v1/layouts -Method Post `
  -Headers $headers -ContentType application/json -Body $body
```

Only public HTTPS image URLs are accepted. `publish` defaults to `false`; the
publisher is never contacted unless it is explicitly true. This synchronous
endpoint is a test surface, not yet a Bubble-ready integration.

For Postman examples, the complete stateless request flow, API-key access and
rotation, route details, errors, and troubleshooting, see
[API_DOCUMENTATION.md](API_DOCUMENTATION.md).

## Streamlit demo

Start the API as shown above, then open a second PowerShell terminal:

```powershell
uv run streamlit run streamlit_app.py
```

Connect to `http://localhost:8080` with the same `LAYOUT_API_KEY`. Choose a
template, describe the layout, and optionally enable publishing. The validated
JSON remains visible and downloadable whether publishing succeeds or fails.

## Cloud Run deployment

Create a runtime service account with only the required Vertex AI access, then
deploy publicly so `/health` works while the `/v1` routes enforce their own
API key:

```powershell
gcloud run deploy layout-test-api --source . `
  --region us-central1 --allow-unauthenticated `
  --service-account "layout-runner@PROJECT_ID.iam.gserviceaccount.com" `
  --cpu 2 --memory 2Gi --concurrency 1 --timeout 900 `
  --min 0 --max 2 `
  --set-env-vars "GOOGLE_CLOUD_PROJECT=PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1,ENABLE_RUN_TRACE=false,LOCAL_OUTPUT=false" `
  --set-secrets "LAYOUT_API_KEY=layout-api-key:1"
```

Use pinned numeric Secret Manager versions, not `latest`. Cloud Run uses the
runtime service account through Application Default Credentials; do not upload
or package a service-account JSON key. Rotate any credential that was ever
included in an archive before deployment. The container build preloads the
CrossEncoder model, and the runtime uses one worker so its cached clients and
model are reused. Warm p50/p95 can be calculated from the structured `request`
and per-stage duration logs after deployment. Publisher URL/key configuration
is optional and should be added only when `publish=true` testing is authorized.

## Publisher demo

To queue each validated layout automatically, set the publisher URL and a
rotated API key in `.env`:

```env
PUBLISHER_API_URL=https://magazine-publisher-0f8b8f449e87.herokuapp.com/api/bubble/queue-job
PUBLISHER_API_KEY=replace-with-rotated-key
```

The local file remains valid JSON. Only the API request wraps it as
`var documentData=<json>`.

## Refresh vector data

```powershell
python -m scripts.prepare_vertex_vector_data
python -m unittest tests.test_layout_pipeline.LocalVectorStoreTests
```

The generated file contains one JSON vector record per line and is packaged in
the application image. Regeneration calls the configured embedding model, so
only run it after the prompt library changes and include it in cost planning.
