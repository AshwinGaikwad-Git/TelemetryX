# TelemetryX Software Testing and Evaluation Report

Engineering evaluation for academic project review | 17 November 2026

TelemetryX combines an industrial monitoring workspace with a separate C-MAPSS research cockpit. This report presents the executed tests, reproduced defects, corrective changes and repeat verification, so a project guide can assess both the implementation and the evidence supporting it.

## Evaluation outcome

The final recorded checks passed: 64 backend cases in each of three post-fix runs, 29 frontend component cases in each of three final runs, and 30 production-browser executions. Both final dependency scans reported zero known findings. Testing reproduced and corrected input-validation, validation-response, text-contrast and sidebar-access problems.

| Verification layer | Recorded final result |
| --- | --- |
| Backend unit and integration | 64 / 64 passed per run; three post-fix runs |
| Frontend components | 29 / 29 passed per run; three final runs |
| Production browser workflows | 30 / 30 passed; five scenarios x three configurations x two iterations |
| Dependency scanning | Zero reported findings in both final scans |

## How to interpret the outcome

These results support a working local evaluation demonstration within the tested scope. They do not prove that the software is error-free, establish production capacity, or validate predictive accuracy on real industrial equipment. Coverage gaps and unexecuted deployment checks are listed explicitly on page 8.

## Tested revision and environment

Base commit 89d919a on feature/industrial-foundation, plus the local cleanup, fixes and evaluation changes. The tested working tree is modified and has not been committed or pushed. A source hash manifest accompanies the evidence.

Windows host; Python 3.12.14; Node.js v26.13.0; Next.js 15.5.29; Vitest 5.1.0; Playwright 1.65.1. Backend tests use temporary SQLite databases. Browser tests use ports 3001 and 8001, disposable storage and a separate optimized Next.js build.

## Test strategy and execution iterations

The campaign began with the existing suites, added adversarial cases, reproduced failures, implemented focused fixes, and repeated full regression checks. A passing retry was not used to conceal a failed case; intermediate results remain in the evidence folder.

| Stage | Evidence and interpretation |
| --- | --- |
| Initial baseline | 45 existing backend cases passed; combined coverage 87%. Existing component baseline contained 21 cases. |
| New adversarial probes | 18 cases: 15 failed and 3 passed before fixes; the same 18 passed after fixes. Multiple failures represent repeated forms of a few underlying defects. |
| Browser discovery | Early runs exposed contrast failures and an unreachable sign-out control. Some timeouts were test-selector assumptions, launch-path issues or development-toolbar interference, not product defects. |
| Expanded regression | 64 backend cases passed in each of three post-fix runs. Run 1 preceded dependency remediation; runs 2 and 3 used the patched Python environment. |
| Final verification | 29 component cases passed three times. Production-browser verification repeated every scenario twice for Chromium desktop, Firefox desktop and mobile Chromium, without automatic retries. |

## Coverage of test types

| Test type | Executed scope |
| --- | --- |
| Functional and integration | Identity, companies, assets, sensors, imports, alerts, maintenance, models, predictions and background jobs |
| Negative and boundary | Malformed inputs, whitespace-only values, non-finite numbers, limits, upload errors, incompatible or stale predictive inputs |
| Security and isolation | Company boundaries, roles, sessions, hostile origins, credential revocation, login throttling and dependency scanning |
| Compatibility and usability | Chromium and Firefox desktop, emulated mobile viewport, keyboard focus, responsive width and sidebar reachability |
| Quality and reliability | Python lint/format/type checks, strict TypeScript, production build, migrations, retries, recovery and repeated runs |

Browser emulation checks a mobile layout and browser profile; it is not a test on a physical Android device. Automated axe checks cover selected rendered states and WCAG rule tags, not a complete accessibility certification.

Sandbox file-access restrictions also interrupted initial test and typing commands. They were rerun with access to isolated temporary files and dependency stubs. These environment failures are excluded from application defect counts.

## Backend defects and corrective analysis

### F01 Required fields accepted blank descriptions

Reproduction: submit a registration with a name or company_name containing only spaces, or pass whitespace-only site names, sensor names/units and work titles. Minimum-length validation accepted the original strings; registration then stripped them after validation, allowing an empty stored identity. The result was blank workspace labels and incomplete asset or maintenance records.

Correction: normalize request text before field constraints through a shared input model. Passwords are excluded because their whitespace is significant. Regression cases cover rejected blanks and valid surrounding whitespace, including proof that passwords remain unchanged. Severity: medium, based on data-integrity impact.

### F02 Email syntax checks were too permissive

Reproduction: a@@example.com, a b@example.com, @example.com and a@example..com passed the previous check, which only looked for an at-sign and a dot in the domain. Such identifiers could produce unusable identity and invitation records.

Correction: apply a stricter practical email syntax check after trimming and lowercasing. The registration and invitation paths share this validation. Negative tests reject the malformed examples and retain normalization for an otherwise valid address. Severity: medium. Syntax validation does not prove address ownership or deliverability; email verification remains outside the pilot.

### F03 Non finite values caused a server error

Reproduction: send raw telemetry JSON containing NaN, Infinity, -Infinity or an overflowing numeric literal. The sensor schema correctly rejected the value, but FastAPI's error details retained the non-finite raw input. JSON error-response serialization then failed, turning an invalid request into a server error.

Correction: a request-validation handler emits only the error type, location and message. Raw inputs and exception context are excluded, producing a valid HTTP 422 response and avoiding accidental credential echoing. All four numeric cases now return parseable JSON. Severity: medium, based on request robustness and diagnostic failure.

### Migration configuration maintenance

Alembic reported deprecated path splitting for prepend_sys_path. Adding path_separator = os makes the intended behavior explicit. The final migration-preservation tests pass after this change. This was a maintenance warning rather than a failed schema migration.

## Frontend and dependency findings

### F04 Secondary text had insufficient contrast

Axe found low-contrast sign-in helper text, inactive tabs, breadcrumbs and research metadata. Examples on the sign-in screen measured approximately 2.5:1 to 4.0:1 against a 4.5:1 normal-text requirement. Repetition after the sample pipeline also exposed a low-contrast rose-colored risk value that was absent from the empty state.

Correction: darken text on light surfaces, retain readable status colors, and adjust the sidebar label on its dark background. Final scans of authentication, industrial overview and research overview reported no violations for the selected WCAG 2 A/AA and 2.1 AA rule tags in all tested configurations. Severity: medium, based on readability and accessibility impact.

### F05 Sign out was unreachable on a short viewport

At the desktop test viewport of 1280 x 720, the fixed sidebar's combined contents extended below the visible screen. The sign-out button existed in the DOM but could not be reached by scrolling the page. The browser test reproduced the resulting inability to sign out through that control.

Correction: enable vertical scrolling inside the sidebar. The final workflow creates data, reloads the page, uses the sign-out button and confirms that the session endpoint returns HTTP 401 afterward. It passes on desktop Chromium, desktop Firefox and mobile Chromium. Severity: medium, based on user-session control.

### F06 Dependency audit findings

The initial npm audit reported 28 findings: 4 critical, 6 high, 17 moderate and 1 low. The initial Python scan reported 24 advisory entries across 5 packages; advisory aliases can overlap, so this is not a count of independent exploitable defects. Scanners identify affected package versions; exploitation was not attempted.

Correction: update Next.js from 15.5.25 to 15.5.29, update Vitest/Vite and their React plugin, and apply patched PostCSS/source-map dependencies. On Python, remove unused FastAPI CLI/cloud extras, keep explicit ASGI and multipart dependencies, and update certifi, PyJWT and pytest. Both final scans report zero known findings. The Next.js image-optimization advisory is condition-dependent, including glibc-based Linux; it was an audit finding, not a reproduced Windows exploit.

### Supporting corrections

Updated the README's obsolete claim that equipment RUL models were unavailable, replaced a deprecated testing-helper release, and made the Vitest configuration explicitly ESM. Windows launch paths, ambiguous selectors and development-overlay interference were corrected in the test harness and are not counted as application defects.

## Final verification and coverage analysis

| Measure | Observed result | Meaning |
| --- | --- | --- |
| Backend line coverage | 91.08% | 2439 of 2678 executable statements reached |
| Backend branch coverage | 72.24% | 393 of 544 branch outcomes reached |
| Backend combined coverage | 87.90% | coverage.py combined line and branch denominator |
| Frontend line coverage | 64.09% | Vitest component instrumentation; browser runs are separate |
| Frontend statement coverage | 61.11% | 473 of 774 statements reached in the recorded component run |
| Frontend branch coverage | 51.79% | 403 of 778 branch outcomes reached |

Coverage describes what the instrumented suites executed; it is not a probability of correctness. The backend combined figure rounds to 88%. The frontend suite reaches substantially more of the industrial workspace than the research page. Layout entry points and less-used research branches remain lightly covered by component tests, although production browser workflows execute both routes.

## Verified behavior by subsystem

| Subsystem | Representative assertions |
| --- | --- |
| Identity and tenancy | Sign-in/out, session revocation, origin rejection, workspace isolation, role restrictions and last-admin protection |
| Telemetry and maintenance | Source checksums, deduplication, invalid units/ranges, stale data, sustained alerts, valid assignees and required completion findings |
| Research and equipment ML | Engine/run holdouts, train-only preprocessing, immutable source snapshots, model compatibility, intervals and stale/out-of-range inference rejection |
| Jobs and persistence | Idempotency, failure/retry/cancel, bounded transient retries, worker recovery interfaces and migration row preservation |
| Build and static checks | Ruff check/format, mypy for app, strict TypeScript with unused declarations, optimized Next.js build and Git whitespace checks |

The repeat runs kept the same acceptance criteria. Browser automatic retries were disabled; all 30 final executions passed without relying on retry-based recovery. Unit/component cases are counted separately from the five browser scenario definitions.

## Performance and local scalability observations

The performance case uses FastAPI TestClient and temporary SQLite, not an external network or a production server. It imports four batches, then runs three read rounds with five concurrent callers and twenty summary requests per round. The table reflects the last recorded backend run; times include local Python, SQLAlchemy and SQLite overhead.

| Readings per batch | Observed time in milliseconds | Acceptance result |
| --- | --- | --- |
| 1 | 28.83 | All submitted readings accepted |
| 10 | 22.76 | All submitted readings accepted |
| 100 | 85.49 | All submitted readings accepted |
| 500 | 258.81 | All submitted readings accepted |

| Read round | Median ms | P95 ms | Requests per second | Errors |
| --- | --- | --- | --- | --- |
| 1 | 45.08 | 54.46 | 105.87 | 0 |
| 2 | 45.5 | 60.77 | 100.72 | 0 |
| 3 | 49.29 | 65.41 | 96.14 | 0 |

### What the measurements show

The tested ingestion sizes completed successfully, and sixty concurrent summary reads completed without HTTP failures or incorrect machine counts. Larger batches take more time because ingestion performs per-reading lookup and persistence work. This identifies batching/database-query optimization as a useful target before scaling to much larger telemetry volumes.

### What the measurements cannot establish

These small samples do not locate a saturation point, measure production network latency or establish an availability target. The reported P95 is the nearest-rank 19th observation among twenty requests, so it is sensitive to individual timings. Coverage instrumentation and other local processes can affect the measurements.

No production-scale stress, multi-hour soak, destructive fault injection, distributed-write concurrency or real Redis/PostgreSQL capacity test was performed. The pilot's maximum import contract is not a demonstrated sustained throughput guarantee.

### Predictive model evaluation boundary

Research workflow tests use the repository's synthetic C-MAPSS-shaped fixtures. Equipment-training tests use controlled labelled fixtures and assert validation/inference contracts. They verify software behavior and data separation, not real-machine reliability, NASA benchmark accuracy or suitability for maintenance decisions.

## Browser evidence and demonstration acceptance

The final browser suite used the optimized Next.js frontend with a migrated disposable API. Chromium and Firefox used desktop profiles; the mobile configuration used Pixel 7 emulation. Each scenario ran twice in each configuration, producing thirty passing executions.

Recorded industrial overview after equipment, telemetry and work-order creation. Screenshots and machine-readable results are retained with the evidence.

| Scenario | Acceptance demonstrated |
| --- | --- |
| Authentication and keyboard | Registration page renders, keyboard focus advances, viewport width fits and selected accessibility checks pass |
| Rejected login | Invalid credentials produce the expected message and the form remains usable |
| Industrial workflow | Create account/site/machine/sensor, import CSV, verify an alert, create work, reload session and sign out |
| Research rendering | Research overview renders in empty or populated state, with selected accessibility and width assertions |
| Sample ML pipeline | Import/preparation, training and prediction jobs finish; model and finite interval-ordered predictions are available |

The first rendering and industrial workflow scenarios also assert absence of uncaught page-level JavaScript exceptions. Backend tests separately exercise alert acknowledgement, recovery and the complete work-order transition rules. A browser workflow pass is not a claim that every button or role permutation was exercised in the browser.

## Limitations and reproducibility

No reproduced application defect remains open from this campaign's final acceptance checks. That conclusion is limited to the recorded test scope. The following items remain relevant for project review and deployment planning.

| Area | Remaining limitation or next verification |
| --- | --- |
| Coverage | Frontend component coverage remains incomplete; prioritize research-page branches and failure-path interactions. Backend uncovered branches include less common error and deployment paths. |
| Deployment | Docker was unavailable. Real PostgreSQL/Redis integration, Linux containers, reverse-proxy/TLS behavior and multi-worker operation were not executed. |
| Accessibility and compatibility | No Safari/WebKit run, physical-device test or full screen-reader audit. Automated axe findings do not constitute complete WCAG conformance. |
| Security | Zero known dependency findings at scan time is not a penetration-test certificate. SSO/MFA, email verification, account recovery and deployment hardening remain outside this pilot. |
| Test tooling | The final backend run retains upstream Starlette/httpx and AnyIO/pytest deprecation warnings. These are recorded warnings, not failed assertions; no warning filters conceal them. |

### Repeat the checks

```powershell
Backend directory: uv sync --all-groups
uv run pytest --cov=app --cov-branch -p no:cacheprovider
uv run ruff check .; uv run ruff format --check .; uv run mypy app
Frontend directory: corepack pnpm install --frozen-lockfile
corepack pnpm test; corepack pnpm typecheck; corepack pnpm build
corepack pnpm exec playwright install chromium firefox
corepack pnpm test:e2e --repeat-each=2
```

The browser configuration currently contains Windows launch paths. Use free ports 3001/8001 and Node.js 22.12 or newer. It creates its own temporary database/storage and .next-evaluation build; it does not use the development database. The report generator requires the isolated ReportLab/PyMuPDF tooling under tmp/report-packages.

### Evidence and references

output/testing/evidence contains JUnit results, browser JSON and HTML reports, coverage summaries, scan output, local-performance.json and evaluation-summary.json. source-manifest.json records SHA-256 values for reviewed application, configuration, test and script files. Re-running commands can replace generated evidence; archive this folder before a new evaluation.

Dependency remediation references: https://github.com/advisories/GHSA-2464-fhr4-w9xw and https://vitest.dev/guide/migration/. Scanner outputs provide the other advisory identifiers and package versions. Project README.md, docs/industrial-pilot.md and docs/cmapss-provenance.md define workflow and prediction boundaries.
