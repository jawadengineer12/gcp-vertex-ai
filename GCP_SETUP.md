# GCP Setup — New Account, From Scratch

This covers everything needed to get the pipeline running on a brand new
Google Cloud account: project creation through the first successful
`python main.py` run and hosted Cloud Run deployment. Semantic retrieval runs
inside the application over the checked-in embedding file; no continuously
deployed Vector Search endpoint is required.

Set these once at the start of your PowerShell session:

```powershell
$PROJECT_ID = "your-google-cloud-project"
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
```

Cloud Run uses this service account directly as its service identity. Do not
create, download, package, or set a service-account JSON key. For local runs,
use Application Default Credentials tied to your own authenticated account:

```powershell
gcloud auth application-default login
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

This optional command makes a paid model request. Skip it unless that test is
explicitly authorized:

```powershell
python -c "from google import genai; c = genai.Client(vertexai=True, project='$PROJECT_ID', location='us-central1'); print(c.models.generate_content(model='gemini-2.5-flash', contents='Hello').text)"
```

## 6. `.env`

Copy `.env.example` to `.env` and fill in:

```env
GOOGLE_CLOUD_PROJECT=your-google-cloud-project
GOOGLE_CLOUD_LOCATION=us-central1
```

## 7. Verify local retrieval data

`normalized_data/vertex_index_data.json` is checked into the repository and
contains the 32 normalized 768-dimensional embeddings used for exact cosine
search. It is loaded and cached once per Cloud Run container. Verify that its
IDs and dimensions match the prompt library:

```powershell
python -m unittest tests.test_layout_pipeline.LocalVectorStoreTests
```

No GCS bucket, Vector Search index, or deployed index endpoint is required.

## 8. Font list

Place the client's exact InDesign font export at `raw_data/Font List.csv`
(already included in this delivery). Only column C (exact InDesign name)
is read — it's the source of truth for every approved font in generation
and validation.

## 9. Run the pipeline

```powershell
python main.py
```

You should see: template selection → prompt → any missing-field questions →
local hybrid retrieval trace → generation attempts → validation → saved output
at `outputs/generated_layout.json` and a full run trace under
`outputs/run_traces/`.

## 10. Run the test suite

```powershell
python -m unittest discover tests
python tests/validate_prompt_library.py
```

Both should pass cleanly before you consider the environment good.

## 11. Deploy the hosted test API to Cloud Run

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
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1,ENABLE_RUN_TRACE=false,LOCAL_OUTPUT=false" `
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
that performs paid embedding and generation calls. `publish=true` additionally
requires a rotated publisher key and contacts the external publisher.

For Postman testing, key access and rotation, the full request/response loop,
and publisher setup behavior, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

### Current hosted verification

On 2026-08-04, local-retrieval revision `layout-test-api-00004-8vd` was
deployed with 100% traffic at:

```text
https://layout-test-api-6euw7jlffa-uc.a.run.app
```

The public health route returned HTTP 200 and a keyless `/v1/templates` request
returned HTTP 401. The publisher URL and pinned secret reference were retained,
the obsolete managed-index variables were removed, and the managed Vector
Search endpoint was confirmed to have no deployed indexes. Local compilation,
24 tests, and prompt-library validation passed.

One authorized end-to-end `publish=false` request then completed successfully
on this revision with one page, five assets, `publisher: null`, and two bounded
validation retries. Server timings were 478 ms retrieval, 60,114 ms reranking
including cold model load, 104,509 ms generation across three attempts, 1 ms
validation, and 165,124 ms total. The managed endpoint still had no deployed
indexes afterward, and no publisher request was made.

The earlier managed-index revision had one authorized cold `publish=false`
generation: one page, five assets, one validation retry, and no publisher
result. Its timings were 687 ms retrieval, 56,700 ms reranking/cold model load,
38,347 ms generation across both attempts, 1 ms validation, and 95,753 ms
total. Treat this only as a historical cold observation, not p50/p95 evidence.

### Existing managed-index rollback

The original managed index is preserved but undeployed, so it has no serving
replicas. The local-retrieval application does not use it. Only redeploy it for
an explicit comparison or when rolling back to the older application code:

```powershell
gcloud ai index-endpoints deploy-index 4607598034195316736 `
  --project=angular-lambda-421320 --region=us-central1 `
  --deployed-index-id=layout_rag_index `
  --display-name=layout_rag_index `
  --index=projects/596225948068/locations/us-central1/indexes/555673385468690432 `
  --machine-type=e2-standard-2 `
  --min-replica-count=1 --max-replica-count=1
```

It is billed continuously while deployed and cannot scale to zero. Undeploy it
immediately after the comparison:

```powershell
gcloud ai index-endpoints undeploy-index 4607598034195316736 `
  --project=angular-lambda-421320 --region=us-central1 `
  --deployed-index-id=layout_rag_index
```

---

## Later: adding new prompt examples

```
1. Append new examples to normalized_data/layout_prompt_library_updated.json
   (scripts/append_excel_to_prompt_library.py if coming from Excel)
2. python -m scripts.prepare_vertex_vector_data   # paid embedding regeneration
3. python -m unittest tests.test_layout_pipeline.LocalVectorStoreTests
4. Deploy the new application image
```

Commit the prompt library and regenerated vector file together so their stable
IDs cannot drift. No hosted index update or serving deployment is required.

## What's out of scope here

- Color palette enforcement — no color list has been provided by the
  client yet (font list only). Add it the same way fonts work
  (`services/font_service.py` pattern) once you have one.
- Fixture assets (masthead/logo/background) — confirmed by the client as
  **not required** on every page; not implemented.
