# Local special-case test report

Run on 2026-08-20 from `feature/special-case-layout-support`. No container was
built, no image was pushed, and no GCP service or production resource was
deployed or modified.

## Automated checks

- 37 unit/integration tests passed.
- Four pre-change normal baselines still validate to identical JSON.
- `git diff --check` passed.

## Live generation

The shared local pipeline generated and validated:

- `special_case_outputs/same_page_threaded_text.json`: one head and one
  same-page continuation sharing an `articleDocumentLink`.
- `special_case_outputs/cross_page_threaded_text.json`: one head followed by
  continuations through page 2.
- `special_case_outputs/image_spread.json`: one 14-inch image originating on
  page 2; page 3 exists and does not duplicate it.

## Local adapters

- CLI generated the pre-change magazine baseline.
- FastAPI `/health` returned 200; real normal and threaded requests completed
  with `publish=false`.
- Streamlit started headlessly against the local API and its health endpoint
  returned 200.

## Publisher testing

The configured publisher testing endpoint accepted all special outputs:

- cross-page thread: `test_1787224157278`
- image spread: `test_1787224159178`
- same-page thread: `test_1787224160137`

The initial normal CLI baseline also queued as `test_1787222384323` because the
existing CLI loaded publisher settings from `.env`.

## Pending manual acceptance

This repository exposes queue submission but no job-status, PDF-download, or
visual-comparison path. PDF rendering and visual confirmation remain pending
in the publisher/testing environment. Deployment remains blocked until that
manual approval is recorded.
