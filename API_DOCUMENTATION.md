# Layout Test API: Postman and Operations Guide

This guide documents the currently deployed synchronous test API. It covers
manual Postman testing, the stateless question/answer flow, API-key management,
publishing behavior, and common errors.

This API is a testing surface. It is not yet declared Bubble-ready, does not
store sessions or request history, and does not accept image uploads.

## Current deployment

| Setting | Value |
| --- | --- |
| Google Cloud project | `angular-lambda-421320` |
| Region | `us-central1` |
| Cloud Run service | `layout-test-api` |
| Base URL | `https://layout-test-api-6euw7jlffa-uc.a.run.app` |
| Verified revision | `layout-test-api-00004-8vd` |
| Runtime service account | `vertex-layout-dev-sa@angular-lambda-421320.iam.gserviceaccount.com` |
| CPU / memory | 2 vCPU / 2 GiB |
| Concurrency / timeout | 1 / 900 seconds |
| Scale | 0 to 2 instances |

Cloud Run permits unauthenticated network access so the health endpoint can be
public. The application itself protects the `/v1` routes with `x-api-key`.

## The API key

The layout API key is a shared secret used only for inbound API authentication.
It is not a Google access token and it is separate from the publisher key.

- Secret Manager secret: `layout-api-key`
- Active version: `1` (enabled)
- Cloud Run mapping: `LAYOUT_API_KEY=layout-api-key:1`
- The value is intentionally not written in this repository or this guide.
- Publisher secret: `publisher-api-key`, pinned version `1`.
- Publisher URL and secret reference are configured on Cloud Run, but no live
  publisher submission has been made from this revision.

### Copy the current key for Postman

You need permission to access the secret, normally
`roles/secretmanager.secretAccessor`.

In Google Cloud Console:

1. Select project `angular-lambda-421320`.
2. Open **Security > Secret Manager**.
3. Open `layout-api-key`.
4. On the **Versions** tab, use the actions menu for version `1` and choose
   **View secret value**.
5. Copy it into a sensitive Postman environment variable. Do not paste it into
   source code, screenshots, tickets, or chat.

Or copy it directly to the Windows clipboard without printing it:

```powershell
$LAYOUT_KEY = gcloud.cmd secrets versions access 1 `
  --secret=layout-api-key `
  --project=angular-lambda-421320
$LAYOUT_KEY.Trim() | Set-Clipboard
Remove-Variable LAYOUT_KEY
```

Official reference: [Access a secret version](https://docs.cloud.google.com/secret-manager/docs/access-secret-version).

### Rotate the key

Rotate it if it may have been exposed, when a team member leaves, or as part of
normal credential maintenance. Adding a version does not automatically switch
this service because the deployment deliberately pins a numeric version.

1. Generate a new high-entropy value in a password manager (at least 32 random
   bytes).
2. In **Secret Manager > layout-api-key**, choose **New version** and paste the
   value. Note the new numeric version, for example `2`.
3. Point Cloud Run at that exact version; this creates a new revision:

   ```powershell
   gcloud.cmd run services update layout-test-api `
     --project=angular-lambda-421320 `
     --region=us-central1 `
     --update-secrets=LAYOUT_API_KEY=layout-api-key:2
   ```

4. Put the new value in Postman and verify `GET /v1/templates` returns `200`.
5. Only after that succeeds, disable the old version:

   ```powershell
   gcloud.cmd secrets versions disable 1 `
     --secret=layout-api-key `
     --project=angular-lambda-421320
   ```

Do not destroy the old version immediately; disabling it is reversible. If a
rollback is needed, re-enable the old version and pin Cloud Run back to it.

Official references: [Add a secret version](https://docs.cloud.google.com/secret-manager/docs/add-secret-version),
[configure Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets),
and [disable a secret version](https://docs.cloud.google.com/secret-manager/docs/delay-destruction-of-secret-versions).

## Postman setup

Create and activate a Postman environment with these variables:

| Variable | Local value | Security |
| --- | --- | --- |
| `base_url` | `https://layout-test-api-6euw7jlffa-uc.a.run.app` | Normal |
| `layout_api_key` | Paste the Secret Manager value | Mark **Secure** and do not add a shared value |

For the collection or each protected request:

1. Open **Authorization**.
2. Choose **API Key**.
3. Set **Key** to `x-api-key`.
4. Set **Value** to `{{layout_api_key}}`.
5. Set **Add to** to **Header**.

For POST requests also add `Content-Type: application/json`. Because generation
is synchronous and a cold request can take over a minute, set Postman's
**Settings > General > Request timeout** to at least `900000` milliseconds while
testing.

Never place the key in the URL or request body.

Postman references: [manage environments](https://learning.postman.com/latest-v-12/docs/use/send-requests/variables/managing-environments),
[API key authorization](https://learning.postman.com/docs/use/send-requests/authorization/authorization-types/),
and [request timeout](https://learning.postman.com/v11/docs/getting-started/installation/settings/).

## Routes and authentication

| Method | Route | Authentication | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | Public | Hosted health check |
| GET | `/healthz` | Public in the app, local use only | Local health alias; Cloud Run currently intercepts this path and returns `404` |
| GET | `/v1/templates` | `x-api-key` required | List templates and their fields |
| POST | `/v1/layouts` | `x-api-key` required | Resolve requirements and generate a layout |
| GET | `/docs` | Public | Swagger UI generated by FastAPI |
| GET | `/redoc` | Public | ReDoc UI generated by FastAPI |
| GET | `/openapi.json` | Public | OpenAPI schema |

The documentation routes expose the schema, not credentials. If only the health
route should be public in a future production API, the documentation routes must
be disabled or protected in a separate change.

### 1. Health check

Create a request with no authorization:

```http
GET {{base_url}}/health
```

Response, `200 OK`:

```json
{
  "status": "ok"
}
```

Use `/health`, not `/healthz`, against Cloud Run.

### 2. List templates

```http
GET {{base_url}}/v1/templates
x-api-key: {{layout_api_key}}
```

Response, `200 OK`:

```json
{
  "templates": [
    {
      "id": "magazine_article",
      "name": "Magazine Article",
      "fields": [
        {
          "name": "article_title",
          "question": "Article title",
          "type": "text",
          "required": true,
          "placeholder": "[article_title]"
        }
      ]
    }
  ]
}
```

The real response contains every field for all four templates:

| Template ID | Field | Type | Required | Question |
| --- | --- | --- | --- | --- |
| `magazine_article` | `article_title` | text | yes | Article title |
|  | `author_name` | text | yes | Author name |
|  | `hero_image_url` | image | no | Hero image HTTPS URL |
| `editorial_page` | `guest_writer_name` | text | yes | Guest writer name |
|  | `guest_writer_photo_url` | image | yes | Guest writer photo HTTPS URL |
|  | `publisher_name` | text | no | Publisher name |
| `cover_page` | `publication_name` | text | yes | Publication name |
|  | `cover_image_url` | image | yes | Cover image HTTPS URL |
|  | `issue_date` | text | no | Issue date |
| `advertisement` | `advertiser_name` | text | no | Advertiser name |
|  | `advertisement_image_url` | image | yes | Advertisement HTTPS URL |

The endpoint response is the source of truth if templates change.

### 3. Create or continue a layout request

```http
POST {{base_url}}/v1/layouts
x-api-key: {{layout_api_key}}
Content-Type: application/json
```

Request fields:

| Field | Type | Rules |
| --- | --- | --- |
| `request_id` | string or null | Optional correlation ID; 1-128 characters using letters, digits, `.`, `_`, `:`, or `-` |
| `prompt` | string | Required, non-empty, maximum 10,000 characters |
| `template_id` | string | Required and must match a template ID |
| `answers` | object | Up to 100 known template-field names; each value is a non-empty string or JSON `null` |
| `publish` | boolean | Optional; defaults to `false` |

The model is strict. For example, use the JSON boolean `false`, not the string
`"false"`. Unknown request properties are rejected.

## Stateless information-gathering flow

The HTTP API replaces the CLI's interactive `InformationAgent` with a stateless
request/response loop. The server uses `RequirementAgent.resolve()` to determine
the fields and `extract_known_values()` to recognize values already present in
the prompt.

There is no server-side session:

1. Send the original prompt, template, empty or accumulated answers, and
   `publish: false`.
2. If values are missing, the API returns `200` with `status: needs_input`.
   Retrieval, reranking, Gemini generation, and publishing are not initialized.
3. Ask the user the returned questions.
4. Resend the same original prompt plus all accumulated answers. Reusing the
   returned `request_id` is recommended for correlation, but it does not restore
   any state.
5. Once every field has either a value or an accepted placeholder, the API runs
   retrieval -> reranking -> sanitization -> Gemini -> validation/retry and
   returns the generated JSON directly.

Answer semantics:

- A string supplies a value.
- JSON `null` accepts that field's standard placeholder, such as
  `[hero_image_url]`.
- An omitted field remains unresolved and will be asked again.
- An answer overrides a value extracted from the prompt.
- Image answers must be public `https://` URLs. Localhost, `.local`, embedded
  credentials, private/non-global IPs, and non-HTTPS URLs are rejected.
- Optional template fields still need a decision: provide a value or send
  `null` to accept their placeholder.

### Example A: initial request needs input

In Postman choose **Body > raw > JSON** and send:

```json
{
  "request_id": null,
  "prompt": "Create a cat article with an image",
  "template_id": "magazine_article",
  "answers": {},
  "publish": false
}
```

Response, `200 OK` (the generated request ID will differ):

```json
{
  "status": "needs_input",
  "request_id": "req_0123456789abcdef",
  "known_values": {},
  "missing_fields": [
    {
      "name": "article_title",
      "question": "Article title",
      "type": "text",
      "required": true,
      "placeholder": "[article_title]"
    },
    {
      "name": "author_name",
      "question": "Author name",
      "type": "text",
      "required": true,
      "placeholder": "[author_name]"
    },
    {
      "name": "hero_image_url",
      "question": "Hero image HTTPS URL",
      "type": "image",
      "required": false,
      "placeholder": "[hero_image_url]"
    }
  ]
}
```

This response is free of paid AI work: it only resolves and extracts fields.

### Example B: resubmit answers and accept a placeholder

Keep the original prompt and copy the returned request ID. Here the two text
questions are answered and the optional image is explicitly declined with
JSON `null`:

```json
{
  "request_id": "req_0123456789abcdef",
  "prompt": "Create a cat article with an image",
  "template_id": "magazine_article",
  "answers": {
    "article_title": "Why Cats Rule the House",
    "author_name": "Moazzam Aleem",
    "hero_image_url": null
  },
  "publish": false
}
```

This request performs paid Vertex AI/Gemini work because all fields are now
resolved. It never contacts the publisher because `publish` is `false`.

Response, `200 OK`:

```json
{
  "status": "completed",
  "request_id": "req_0123456789abcdef",
  "layout": {},
  "publisher": null,
  "timing_ms": {
    "retrieval": 687,
    "reranking": 56700,
    "generation": 38347,
    "validation": 1,
    "total": 95753
  }
}
```

`layout` contains the full validated layout project; `{}` is abbreviated here.
Stage timings vary, especially on a scale-to-zero cold start. The currently
deployed revision has already completed a live `publish:false` request.

### Example C: provide a public image URL

Replace the null answer with a public URL:

```json
"hero_image_url": "https://images.example.com/cat.jpg"
```

The API validates the URL form but does not host or upload the image. The
consumer of the generated layout must be able to fetch that URL publicly.

### Example D: answers override prompt extraction

If the prompt contains an author but the answer object supplies a different
one, the answer wins:

```json
{
  "prompt": "Write Cats at Home by First Author",
  "template_id": "magazine_article",
  "answers": {
    "author_name": "Final Author"
  },
  "publish": false
}
```

If other fields remain unresolved, the response returns `needs_input` with
`known_values.author_name` set to `Final Author`.

## Publishing

For tests that must not contact the publisher, send:

```json
"publish": false
```

That guarantees the publisher is not contacted and `publisher` is `null` in a
completed response.

Revision `layout-test-api-00004-8vd` has the HTTPS publisher URL and
`PUBLISHER_API_KEY=publisher-api-key:1` configured. This configuration has been
verified without displaying the key value or submitting a publisher job. An
end-to-end `publish:false` request completed successfully using exact local
vector retrieval and returned `publisher:null`. Sending `publish:true` performs
paid generation and then contacts the real publisher.

A successful `publish:true` response includes the publisher HTTP status and
response body:

```json
"publisher": {
  "status_code": 200,
  "body": "..."
}
```

If generation succeeds but submission fails, the API returns `502` while
preserving the generated layout:

```json
{
  "status": "publish_failed",
  "request_id": "req_0123456789abcdef",
  "layout": {},
  "publisher": null,
  "timing_ms": {
    "retrieval": 0,
    "reranking": 0,
    "generation": 0,
    "validation": 0,
    "total": 0
  },
  "error": "Publisher submission failed"
}
```

`PUBLISHER_API_KEY` must remain a different secret from `LAYOUT_API_KEY`.

## Status codes and validation errors

| Status | Meaning | Typical response or action |
| --- | --- | --- |
| `200` | Health, templates, `needs_input`, or `completed` | Check the response `status` for layout calls |
| `401` | Missing or wrong `x-api-key` | `{"detail":"Invalid API key"}`; verify the header and Postman environment |
| `422` | Strict request validation failed | Read `detail`; common causes are an unknown template/answer, empty or oversized text, extra properties, wrong JSON types, or an invalid image URL |
| `502` | Generation failed, or publishing failed after generation | Retry only after reading logs; `publish_failed` includes the generated layout |
| `503` | Server API-key or publisher configuration is missing from the active revision | Inspect Cloud Run variables and secret references |

Useful `422` examples:

```json
{"detail":"Unknown template_id"}
```

```json
{"detail":"Unknown answer fields: made_up_field"}
```

```json
{"detail":"Image values must be public HTTPS URLs: hero_image_url"}
```

Pydantic shape/type failures return a `detail` array identifying the failing
field. A `200 needs_input` response is normal interaction, not an error.

## Viewing Cloud Run logs

The service writes structured logs containing request ID, stage, duration,
retry count, and result. It deliberately does not log prompts, generated text,
image URLs, or credentials.

Console path:

1. Open **Cloud Run > layout-test-api > Logs**.
2. Filter by a request ID copied from the response, for example
   `req_0123456789abcdef`.

CLI example:

```powershell
gcloud.cmd logging read `
  'resource.type="cloud_run_revision" AND resource.labels.service_name="layout-test-api" AND textPayload:"req_0123456789abcdef"' `
  --project=angular-lambda-421320 `
  --limit=50 `
  --format=json
```

Expected stages include requirements, retrieval, reranking, generation,
validation, publisher when enabled, and the overall request. Use the returned
`timing_ms` for per-request timings and aggregated logs for warm p50/p95.

## Troubleshooting checklist

- `404` on `/healthz`: use `GET /health` on Cloud Run.
- `401`: confirm Postman sent `x-api-key`, not `Authorization`, and that the
  intended environment is active with a local key value.
- `422`: inspect `detail`; do not send unknown fields, string booleans, HTTP
  image URLs, or omitted unresolved fields.
- Repeated `needs_input`: resend every accumulated answer; the server stores no
  previous request state. Use JSON `null` to accept a placeholder.
- Long request: generation is synchronous. Increase Postman's timeout and allow
  for a scale-to-zero cold start plus reranker loading.
- `503` with `publish:true`: publisher configuration is missing or inaccessible
  in the active revision; inspect its URL, secret reference, and IAM access.
- `502`: keep the request ID and inspect Cloud Run logs. Do not blindly retry a
  `publish:true` request because the external publisher may have accepted it
  before a response failed.

## Security summary

- Treat the layout key as a password and rotate it after any exposure.
- Keep the layout and publisher keys separate.
- Store deployed secrets in Secret Manager with pinned numeric versions.
- Do not put secrets in `.env.example`, Git, container images, Postman shared
  initial values, screenshots, or URLs.
- Cloud Run uses its service account and Application Default Credentials; do
  not deploy a service-account JSON file.
- Use only public HTTPS image URLs.
- Keep `publish:false` until publisher testing is explicitly authorized.
- Any credential that was previously included in an archive is compromised and
  must be rotated externally.
