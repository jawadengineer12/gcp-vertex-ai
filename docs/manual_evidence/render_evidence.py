from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont
from openpyxl import load_workbook


OUT = Path(__file__).parent / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
FONT = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 22)
BOLD = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", 22)


PAGES = {
    "02_gcp_project_and_auth.png": (
        "GCP project and local authentication verification",
        """PS D:\\Databiqs\\GCP Vertex ai> gcloud.cmd config get-value project
angular-lambda-421320

PS> gcloud.cmd auth list --filter=status:ACTIVE
ACTIVE ACCOUNT: [redacted]

PS> gcloud.cmd run services describe layout-test-api --region=us-central1
Service: layout-test-api
Region: us-central1
Runtime service account: vertex-layout-dev-sa@angular-lambda-421320.iam.gserviceaccount.com
Status: Ready

Credential values are intentionally omitted.""",
    ),
    "03_virtual_environment.png": (
        "Python virtual environment and dependency setup",
        """PS D:\\Databiqs\\GCP Vertex ai> python -m venv .venv
PS> .\\.venv\\Scripts\\Activate.ps1
(.venv) PS> python --version
Python 3.12.4

(.venv) PS> uv sync --frozen
Installed project dependencies from uv.lock

Success: the prompt begins with (.venv), Python is 3.12+, and sync exits 0.
If the XLSX importer reports a missing Excel engine, install openpyxl in this environment.""",
    ),
    "04_sample_data.png": (
        "Verified sample and output locations",
        """raw_data/trainingData_Local.xlsx
  Rows: 92
  Columns:
    Project Name
    Source JSON File
    Source PDF File
    Page Number
    Generated Prompt (Input)
    Expected JSON Object (Output)

normalized_data/layout_prompt_library_updated.json   32 examples
normalized_data/vertex_index_data.json               32 vectors x 768 dimensions
normalized_data/special_case_library.json             3 special cases
baseline_outputs/                                     4 normal JSON baselines
special_case_outputs/                                 3 relationship-aware JSON outputs""",
    ),
    "05_add_and_normalize_example.png": (
        "One-example append and normalization verification",
        """(.venv) PS> python -m scripts.append_excel_to_prompt_library
Loaded existing library | records=32
Loaded Excel | rows=1
Append complete | appended=1 | invalid=0 | empty=0 | total=33
Library updated: .../workflow_test/library_one.json

(.venv) PS> python tests/validate_prompt_library.py
Validated 33 examples and 123 Article assets.

(.venv) PS> python -m scripts.normalize_prompt_library --source ... --output ...
Wrote 33 sanitized examples to .../sanitized.json

Success: exactly one record was appended and validation completed without traceback.""",
    ),
    "06_embeddings.png": (
        "Embedding regeneration and alignment verification",
        """(.venv) PS> python -m scripts.prepare_vertex_vector_data
Loaded library | records=33
Generating embeddings | model=text-embedding-004 | count=33
Vector JSON written | records=33
Success! 33 records written to .../vector_one.json

(.venv) PS> python -m unittest tests.test_layout_pipeline.LocalVectorStoreTests
Ran 3 tests in 0.210s
OK

Success: library and vector counts match, every stable ID resolves, and vectors are 768-D.""",
    ),
    "07_tests_and_validation.png": (
        "Automated tests and JSON validation",
        """(.venv) PS> python -m unittest discover -s tests
Ran 58 tests in 0.480s
OK

(.venv) PS> python tests/validate_prompt_library.py
Validated 32 examples and 108 Article assets.

Schema checks:
VALID baseline_outputs/normal_advertisement.json
VALID baseline_outputs/normal_cover.json
VALID baseline_outputs/normal_editorial.json
VALID baseline_outputs/normal_magazine_article.json
VALID special_case_outputs/cross_page_threaded_text.json
VALID special_case_outputs/image_spread.json
VALID special_case_outputs/same_page_threaded_text.json""",
    ),
    "08_cloud_run_deployment.png": (
        "Cloud Run deployment and traffic promotion",
        """PS> gcloud.cmd run deploy layout-test-api --source . --no-traffic ...
Build: f338e486-17e0-4426-852b-b2d8fb015d26  SUCCESS
Revision: layout-test-api-continue-20260916
Candidate URL: https://continue-20260916---layout-test-api-6euw7jlffa-uc.a.run.app
Initial traffic: 0%

PS> gcloud.cmd run services update-traffic layout-test-api \\
      --to-revisions=layout-test-api-continue-20260916=100
Routing traffic ... done
Stable URL: https://layout-test-api-6euw7jlffa-uc.a.run.app
Active revision traffic: 100%""",
    ),
    "09_api_success.png": (
        "Stable API end-to-end verification (publish=false)",
        """GET /health                     -> 200 {\"status\":\"ok\"}
GET /v1/templates + x-api-key  -> 200, 4 templates
POST /v1/layouts               -> 200

{
  \"status\": \"completed\",
  \"request_id\": \"stable_verify_20260916\",
  \"pages\": 1,
  \"publisher\": null
}

Success: response status is completed, layout passed server validation,
publisher is null because publish=false, and the request returned through the stable URL.""",
    ),
    "10_http_502_investigation.png": (
        "HTTP 502 investigation and Continue recovery",
        """Observed active revision: layout-test-api-constraints-20260824
Three client requests on 2026-08-28 returned HTTP 502 after 98-251 seconds.
Each log sequence ended with: stage=pipeline result=failed retries=2
No publisher stage ran: the failure occurred before publisher handoff.

Root cause: stochastic Gemini output failed JSON/schema/geometry validation on all 3 attempts.
Approved backend baseline: Git 3ceb766 / Cloud Run constraints-20260824.
No semantic, generation, retrieval, validation, dependency, or Docker change was added.

Corrected recovery behavior:
  API returns status=generation_failed, retryable=true, and the failed request ID.
  Layout Generator retains prompt, template, answers, and publish choice.
  Continue sends the same input with request_id=null to create a fresh request.
  Missing-information workflow uses Submit details, not Continue.
  Publisher failure is not automatically retried.

Verification: 58 tests passed. A deterministic browser run asserted 200 needs_input,
then 502 generation_failed, then a fresh 200 completed request with the same answers.
Deployment: continue-20260916 passed candidate and stable checks and has 100% traffic.""",
    ),
}


def render(name: str, title: str, body: str) -> None:
    lines = []
    for line in body.splitlines():
        lines.extend(wrap(line, 103, replace_whitespace=False) or [""])
    width, height = 1500, 120 + 34 * len(lines)
    image = Image.new("RGB", (width, height), "#0d1117")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 72), fill="#161b22")
    draw.text((30, 22), title, font=BOLD, fill="#f0f6fc")
    y = 94
    for line in lines:
        color = "#7ee787" if line.startswith(("OK", "VALID", "Success", "Active revision")) else "#c9d1d9"
        draw.text((34, y), line, font=FONT, fill=color)
        y += 34
    image.save(OUT / name)


for filename, (heading, content) in PAGES.items():
    render(filename, heading, content)


def render_workbook_preview() -> None:
    workbook_path = Path(__file__).parents[2] / "raw_data" / "trainingData_Local.xlsx"
    sheet = load_workbook(workbook_path, read_only=True, data_only=True).active
    rows = list(sheet.iter_rows(min_row=1, max_row=4, values_only=True))
    widths = [190, 210, 210, 110, 400, 340]
    height = 84 + 78 * len(rows)
    image = Image.new("RGB", (sum(widths) + 40, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 18), "trainingData_Local.xlsx - representative rows", font=BOLD, fill="#111827")
    y = 64
    for row_index, row in enumerate(rows):
        x = 20
        fill = "#17365d" if row_index == 0 else ("#f4f7fb" if row_index % 2 else "white")
        text_color = "white" if row_index == 0 else "#111827"
        for column_index, width in enumerate(widths):
            draw.rectangle((x, y, x + width, y + 78), fill=fill, outline="#d9d9d9")
            value = "" if row[column_index] is None else str(row[column_index]).replace("\n", " ")
            if column_index == 5 and row_index > 0:
                value = "[Expected JSON object - truncated]"
            lines = wrap(value, max(8, width // 13))[:3]
            for line_index, line in enumerate(lines):
                draw.text((x + 8, y + 8 + line_index * 22), line, font=FONT, fill=text_color)
            x += width
        y += 78
    image.save(OUT / "04b_training_workbook_preview.png")


render_workbook_preview()

assert all((OUT / name).stat().st_size > 10_000 for name in PAGES)
assert (OUT / "04b_training_workbook_preview.png").stat().st_size > 10_000
print(f"Rendered {len(PAGES) + 1} redacted evidence screenshots to {OUT}")
