# GCP Setup — New Account, From Scratch

This covers everything needed to get the pipeline running on a brand new
Google Cloud account: project creation through the first successful
`python main.py` run. It extends `docs/Vertex AI Development Setup Guide
From Scratch.docx` (written for the old `indesign-layout-ai` project) with
the Vector Search pieces that guide didn't cover yet.

Set these once at the start of your PowerShell session:

```powershell
$PROJECT_ID = "your-google-cloud-project"
$VECTOR_BUCKET = "gs://${PROJECT_ID}-vector-data"
```

---

## 1. Project, billing, and CLI

```powershell
gcloud auth login
gcloud projects create $PROJECT_ID
gcloud config set project $PROJECT_ID
```

Link billing in the Console: **Billing → Link a billing account**.

## 2. Enable required APIs

```powershell
gcloud services enable `
  aiplatform.googleapis.com `
  artifactregistry.googleapis.com `
  cloudbuild.googleapis.com `
  run.googleapis.com `
  secretmanager.googleapis.com `
  iam.googleapis.com `
  storage.googleapis.com `
  cloudresourcemanager.googleapis.com `
  serviceusage.googleapis.com
```

## 3. Service account

```powershell
gcloud iam service-accounts create vertex-layout-dev-sa `
  --display-name="Vertex Layout Dev SA"

$SA_EMAIL="vertex-layout-dev-sa@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$SA_EMAIL" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$SA_EMAIL" --role="roles/storage.objectAdmin"

mkdir secrets
gcloud iam service-accounts keys create secrets/gcp-sa-key.json `
  --iam-account=$SA_EMAIL
```

`secrets/` is already in `.gitignore` — never commit this key. This JSON key is
for local CLI development only. Cloud Run must use the service account directly
as its service identity; never set `GOOGLE_APPLICATION_CREDENTIALS` on Cloud Run.

Set credentials for local runs:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="secrets/gcp-sa-key.json"
```

## 4. Python environment

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -e .
```

(`pyproject.toml` already lists every dependency — `google-genai`,
`google-cloud-aiplatform`, `google-cloud-storage`, `pydantic`,
`python-dotenv`, `pandas`, `numpy`, `sentence-transformers`.)

## 5. Confirm Gemini access

```powershell
python -c "from google import genai; c = genai.Client(vertexai=True, project='$PROJECT_ID', location='us-central1'); print(c.models.generate_content(model='gemini-2.5-flash', contents='Hello').text)"
```

## 6. `.env`

Copy `.env.example` to `.env` and fill in:

```env
GOOGLE_CLOUD_PROJECT=your-google-cloud-project
GOOGLE_CLOUD_LOCATION=us-central1
GCS_VECTOR_BUCKET_URI=gs://your-google-cloud-project-vector-data
```

Leave `VERTEX_API_ENDPOINT`, `VERTEX_INDEX_ENDPOINT`, and
`VERTEX_DEPLOYED_INDEX_ID` blank for now — steps 8–10 produce them.

## 7. Create the GCS bucket for vector data

```powershell
gcloud storage buckets create $VECTOR_BUCKET `
  --location=us-central1 --uniform-bucket-level-access
```

## 8. Generate embeddings and upload

```powershell
python -m scripts.prepare_vertex_vector_data
gcloud storage cp normalized_data/vertex_index_data.json $VECTOR_BUCKET/
```

This embeds all 32 prompt library entries and writes
`normalized_data/vertex_index_data.json` as newline-delimited JSON in the
`{"id", "embedding"}` format Vector Search requires. The `.json` extension
is required by the batch import service.

If replacing a previous upload that used the unsupported `.jsonl` extension,
remove that stale object first:

```powershell
gcloud storage rm "${VECTOR_BUCKET}/vertex_index_data.jsonl"
```

## 9. Create the Vector Search index

```powershell
python -m scripts.create_cloud_index
```

This takes 15–30 minutes. It prints an index resource name like:

```
projects/123456789/locations/us-central1/indexes/1234567890123456789
```

Save that as `VERTEX_INDEX_RESOURCE_NAME` in `.env` — you'll need it later
whenever you add new examples via `scripts/update_vector_index.py`.

## 10. Deploy an index endpoint

The index isn't queryable until it's deployed behind an endpoint.

```powershell
gcloud ai index-endpoints create `
  --display-name=layout-rag-endpoint `
  --region=us-central1 `
  --public-endpoint-enabled

gcloud ai index-endpoints deploy-index INDEX_ENDPOINT_ID `
  --deployed-index-id=layout_rag_index `
  --display-name=layout_rag_index `
  --index=INDEX_RESOURCE_NAME_FROM_STEP_9 `
  --region=us-central1
```

Deployment takes another 15–30 minutes. When it finishes:

```powershell
gcloud ai index-endpoints describe INDEX_ENDPOINT_ID --region=us-central1
```

Copy three values into `.env`:

- `VERTEX_API_ENDPOINT` — the `publicEndpointDomainName` field
- `VERTEX_INDEX_ENDPOINT` — the full endpoint resource name
  (`projects/.../locations/.../indexEndpoints/...`)
- `VERTEX_DEPLOYED_INDEX_ID` — `layout_rag_index` (what you set with
  `--deployed-index-id` above)

Verify that `deployedIndexes` is present in the description before testing a
completed generation request. An endpoint without a deployed index can serve
the API's question flow but cannot perform vector retrieval. A deployed Vector
Search index has ongoing cost, so do not leave an unused deployment running.

## 11. Font list

Place the client's exact InDesign font export at `raw_data/Font List.csv`
(already included in this delivery). Only column C (exact InDesign name)
is read — it's the source of truth for every approved font in generation
and validation.

## 12. Run the pipeline

```powershell
python main.py
```

You should see: template selection → prompt → any missing-field questions →
hybrid retrieval trace → generation attempts → validation → saved output
at `outputs/generated_layout.json` and a full run trace under
`outputs/run_traces/`.

## 13. Run the test suite

```powershell
python -m unittest discover tests
python tests/validate_prompt_library.py
```

Both should pass cleanly before you consider the environment good.

## 14. Deploy the hosted test API to Cloud Run

The hosted API is synchronous and stateless. It is a testing surface, not yet
declared Bubble-ready. Cloud Run builds the checked-in `Dockerfile` remotely,
including the cached CrossEncoder model; a local Docker build is optional.

Create or reuse a dedicated runtime service account and grant only the access
the pipeline needs:

```powershell
$RUN_SA="vertex-layout-dev-sa@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$RUN_SA" `
  --role="roles/aiplatform.user"
```

Create the required Secret Manager secret for inbound API authentication.
Generate/rotate its value outside the repository:

```powershell
gcloud secrets create layout-api-key --replication-policy=automatic
gcloud secrets versions add layout-api-key --data-file=-

gcloud secrets add-iam-policy-binding layout-api-key `
  --member="serviceAccount:$RUN_SA" `
  --role="roles/secretmanager.secretAccessor"
```

Publisher configuration is optional. Leave it absent for JSON-only operation
and keep `publish=false`. If publishing is enabled later, create a separate
`publisher-api-key`; never reuse the layout API key.

Use numeric Secret Manager versions in the deployment, never `latest`:

```powershell
gcloud run deploy layout-test-api --source . `
  --project=$PROJECT_ID --region=us-central1 --allow-unauthenticated `
  --service-account=$RUN_SA `
  --cpu=2 --memory=2Gi --concurrency=1 --timeout=900 `
  --min=0 --max=2 `
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1,VERTEX_API_ENDPOINT=$VECTOR_API_ENDPOINT,VERTEX_INDEX_ENDPOINT=$VECTOR_INDEX_ENDPOINT,VERTEX_DEPLOYED_INDEX_ID=layout_rag_index,ENABLE_RUN_TRACE=false,LOCAL_OUTPUT=false" `
  --set-secrets="LAYOUT_API_KEY=layout-api-key:1"
```

The repository's `.gcloudignore` excludes `.env`, `secrets/`, service-account
JSON, virtual environments, logs, outputs, caches, and archives from source
uploads.

Cloud Run reserves some paths ending in `z`, so the hosted health endpoint is
`GET /health`. The required `GET /healthz` route remains available when running
FastAPI locally. Verify the deployed no-paid-call flow:

```powershell
$SERVICE_URL = gcloud run services describe layout-test-api `
  --project=$PROJECT_ID --region=us-central1 --format="value(status.url)"
$LAYOUT_KEY = gcloud secrets versions access 1 --secret=layout-api-key
$HEADERS = @{ "x-api-key" = $LAYOUT_KEY }

Invoke-RestMethod "$SERVICE_URL/health"
Invoke-RestMethod "$SERVICE_URL/v1/templates" -Headers $HEADERS

$BODY = @{
  request_id = $null
  prompt = "Create a cat article with an image"
  template_id = "magazine_article"
  answers = @{}
  publish = $false
} | ConvertTo-Json

Invoke-RestMethod "$SERVICE_URL/v1/layouts" -Method Post `
  -Headers $HEADERS -ContentType application/json -Body $BODY
```

The final call must return `needs_input`; it does not initialize Vertex,
Gemini, or the reranker. Ask before sending a fully resolved request because
that performs paid retrieval and generation. `publish=true` additionally
requires a rotated publisher key and contacts the external publisher.

For Postman testing, key access and rotation, the full request/response loop,
and publisher setup behavior, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

### Current hosted verification

On 2026-08-03, revision `layout-test-api-00002-kfn` was verified at:

```text
https://layout-test-api-6euw7jlffa-uc.a.run.app
```

The public health check, API-key rejection, template listing, and stateless
`needs_input` flow passed. One authorized cold `publish=false` generation also
completed with one page, five assets, no publisher result, and one validation
retry. Server timings were 687 ms retrieval, 56,700 ms reranking/cold model
load, 38,347 ms generation across both attempts, 1 ms validation, and 95,753 ms
total. Treat this as one cold observation, not p50/p95 evidence; collect a
larger warm sample before making latency claims. Publisher variables and
credentials are intentionally absent from this revision.

---

## Later: adding new prompt examples

```
1. Append new examples to normalized_data/layout_prompt_library_updated.json
   (scripts/append_excel_to_prompt_library.py if coming from Excel)
2. python -m scripts.prepare_vertex_vector_data   # regenerates full vector JSON
3. python -m scripts.update_vector_index          # upserts into the live index
```

No index rebuild needed for incremental additions — only step 9 (full
recreate) if you ever need to change the embedding dimensions or start over.

## What's out of scope here

- Color palette enforcement — no color list has been provided by the
  client yet (font list only). Add it the same way fonts work
  (`services/font_service.py` pattern) once you have one.
- Fixture assets (masthead/logo/background) — confirmed by the client as
  **not required** on every page; not implemented.
