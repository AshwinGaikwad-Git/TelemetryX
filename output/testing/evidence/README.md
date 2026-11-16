# TelemetryX evaluation evidence

Report date: 17 November 2026. All application tests use disposable fixtures and databases. The local webpage smoke check only reads the running development services.

| Evidence | Purpose |
| --- | --- |
| `backend-baseline.xml` and `.txt` | Original 45-case baseline and initial coverage |
| `adversarial-before.xml` and `adversarial-after.xml` | Reproduction and correction of 18 negative/normalization cases |
| `backend-final1.xml` through `backend-final3.xml` | Three 64-case post-fix runs; run 1 precedes dependency updates |
| `frontend-final1.xml` through `frontend-final3.xml` | Three 29-case final component runs |
| `browser-results.json` and `browser-final.txt` | Thirty passing production-browser executions with retries disabled |
| `browser-report/index.html` | Interactive final Playwright report |
| `browser-*before*` and `browser-iteration*` | Discovery runs including product findings and corrected harness assumptions |
| `screenshot-verification.txt` | Three additional workflow passes used to refresh report screenshots |
| `backend-coverage.json` and `backend-coverage/index.html` | Backend line and branch coverage from final run 2 |
| `frontend-coverage/coverage-summary.json` and `index.html` | Component coverage; separate from browser execution |
| `frontend-audit-before.json` and `frontend-audit-final.json` | npm advisory counts before and after remediation |
| `backend-audit-before.json` and `backend-audit-after.json` | Python advisory output before and after remediation |
| `quality-checks.json` | Actual return codes and output for lint, formatting, typing and whitespace checks |
| `local-performance.json` | Three local read rounds and four ingestion sizes from the final backend run |
| `production-build.txt` and `live-smoke.json` | Optimized build and HTTP checks for the running services |
| `evaluation-summary.json` and `source-manifest.json` | Consolidated results and SHA-256 source file hashes |

Some raw PowerShell captures are UTF-16 and include tool stderr. The JSON advisory metadata and JUnit/browser assertions are the authoritative result fields; a PowerShell wrapper status alone is not used as a pass/fail count. Initial infrastructure access errors are not application defects. Intermediate discovery captures contain intentional test failures. The final results files distinguish them from the passing acceptance runs.

The screenshots show disposable evaluation accounts and synthetic telemetry. Predictive fixtures establish software behavior, not real equipment accuracy. Existing source cleanup changes were already present before this testing campaign; they are not counted as newly discovered testing defects.

Re-running the tests can overwrite these files. Archive this folder before collecting a new evaluation run.
