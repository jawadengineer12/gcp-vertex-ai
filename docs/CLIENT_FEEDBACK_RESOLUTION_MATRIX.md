# Client feedback resolution matrix

Verified 16 September 2026. Phase 1 only. The runtime baseline is Git commit `3ceb766`, matching Cloud Run revision `layout-test-api-constraints-20260824`; the only approved runtime delta is the retryable 5xx Continue behavior.

| Review comment | Resolution | Evidence/manual location |
|---|---|---|
| Repository link correct | Reverified the live GitHub URL and default `main` branch. The repository was publicly visible at verification time. | Manual §2.1; screenshot 01 |
| Show cloud roles/account onboarding | Added GCP login, project selection, ADC, verified runtime identity, known runtime roles, success/failure checks, and an explicit note that organization deployer roles are not fully enumerated. | §2.3; screenshot 02 |
| Cover both sample update paths | Added normal XLSX/corpus workflow and separate relationship-aware special-case workflow. | §§7–8 |
| Future developers deploy Cloud Run directly | Added zero-traffic deploy, candidate verification, promotion, rollback evidence, and stable verification. | §11; screenshot 08 |
| Clarify publisher handoff | Defined the external queue POST, envelope, opt-in controls, and repository boundary. | §10.3 |
| Screenshots for listed areas | Added GitHub and Swagger captures, redacted GCP/auth and terminal evidence, sample workbook structure, maintenance/test/deployment evidence, and deterministic Streamlit retry-Continue and completion captures. Secret values remain masked. | Throughout; `docs/manual_evidence/screenshots/` |
| Troubleshoot HTTP 502 before Phase 2 | Reproduced the pre-publisher validation exhaustion from logs. The API now marks exhausted generation as retryable, and Layout Generator preserves all input and offers Continue to start a fresh request. No unrelated backend or Docker change is included. The focused revision passed candidate and stable checks and now receives 100% traffic. | §12; screenshots 8–11, 13 |
| Does Henry have private-repository access? | Repository is currently public; specific ownership/onboarding responsibility and Henry’s account status are not in the repository and remain an organizational check. | §2.1; unverified list |
| Where do excluded items/folders reside? | Repository map and `.gcloudignore` behavior added; runtime-only/excluded outputs and secrets identified. | §§3, 11.1, 13 |
| Verify primary implementation files in GitHub | Verified `main.py`, `api.py`, `streamlit_app.py`, `core/`, `services/`, `schemas/`, scripts, and tests. | §§1, 3; screenshot 01 |
| Verify local credentials; screenshots | Added `gcloud.cmd auth login`, project selection, ADC, service identity explanation, and redacted evidence. | §2.3; screenshot 02 |
| Establish a virtual environment first | Added venv creation/activation before installation and all run commands, with activation fallback. | §4.1; screenshot 03 |
| Verify hosted API URL and key | URL verified live. Key value is intentionally omitted; documented Secret Manager location. The key printed in client review must be rotated. | Cover, §§2.3, 13 |
| Are baseline/special outputs on GCP Drive? | No: verified as checked-in repository directories; not automatically GCS-hosted. | §3 |
| Confirm raw_data and show XLSX | Verified `raw_data/trainingData_Local.xlsx`, 92 rows, six columns; included redacted structural evidence. | §7.1; screenshot 04 |
| Clarify environment for append script | Repository root, active Python venv, `EXCEL_FILE_PATH`, exact command, expected counts, and failure checks added. | §7 |
| Where are special-case folders? | Source library, outputs, tests, and report locations documented. | §§3, 6, 8 |
| Template/requirement tests: which environment? | Active venv and repository root stated; full test, special-case, and representative commands supplied. | §§4, 8–9 |
| Run test suite plus representative generations | Reran the exact baseline suite after the focused change: 58 tests passed. Prompt validation passed for 32 examples and 108 Article assets. The baseline has no demo-matrix scripts; the manual documents the verified test commands and the interactive non-publishing CLI command for a live representative generation. | §9 |
| How to verify JSON passes? | Defined API/CLI success criteria, direct schema command, validation scope, and failure behavior. | §§5–6 |
| Is verification through Layout Generator? | Corrected the intended workflow: missing information uses Submit details. After a retryable generation 5xx, Layout Generator displays Continue and starts a fresh request with the retained prompt, template, answers, and publish choice. A deterministic failed-first/success-second browser run verified the UI and request payloads. | §§5, 11.3–11.4; screenshots 11/13 |
| Configure Local/GCS/Publisher output | Added exact configuration keys, behavior, success indicators, and failure checks. | §10 |
| Resolve demo 502 | Reproduced the historical generation/validation exhaustion and added the requested user-controlled retry. The first failed request retains its inputs; Continue submits a fresh request ID with the same values. Publisher failures are excluded to prevent duplicate jobs. Local 58-test and deterministic browser checks pass; candidate and stable Cloud Run checks also pass. | §12; screenshots 8–11/13 |
| Clarify “branch” | Defined and provided commands and success criteria. | §2.2; glossary |
| Guided new-developer exercise | Added repository access through one example, normalization, embeddings, tests, generation, JSON validation, zero-traffic deployment, and API/Layout Generator verification with success indicators. | §14 |

## Items not fully verified

- The organization’s designated repository/access owner and whether Henry’s specific GitHub account has been onboarded. The repository was public during verification, but account ownership is not recorded in code.
- The external publisher dashboard, job-status polling, generated-PDF retrieval, and downstream acceptance criteria. Those systems are outside this repository.
- A new live `publish=true` submission was not made because it would create a real external publisher job. Historical hardened-revision logs show successful publisher stages; current generation/API verification used `publish=false`.
- Exact organization-specific IAM roles for every future human deployer. Runtime model and secret-access roles are verified; deployer grants depend on the client’s IAM policy.
- The exposed inbound API key found in the review PDF was not rotated because rotation would invalidate existing client integrations and needs coordinated rollout. It should be rotated promptly.
