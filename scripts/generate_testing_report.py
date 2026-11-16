"""Build the evaluation report from recorded test evidence, with a matching editable copy."""

import hashlib
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tmp/report-packages"))

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

EVIDENCE = ROOT / "output/testing/evidence"
OUTPUT = ROOT / "output/pdf/TelemetryX_Software_Testing_and_Evaluation_Report.pdf"


def read_json(path):
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-16" if raw.startswith(b"\xff\xfe") else "utf-8"))


def junit(name):
    root = ET.parse(EVIDENCE / name).getroot()
    cases = root.findall(".//testcase")
    failures = sum(c.find("failure") is not None or c.find("error") is not None for c in cases)
    return {"tests": len(cases), "failures": failures, "cases": [c.attrib for c in cases]}


backend = [junit(f"backend-final{i}.xml") for i in (1, 2, 3)]
frontend = [junit(f"frontend-final{i}.xml") for i in (1, 2, 3)]
browser = read_json(EVIDENCE / "browser-results.json")
assert all(r["tests"] == 64 and not r["failures"] for r in backend)
assert all(r["tests"] == 29 and not r["failures"] for r in frontend)
assert browser["stats"]["expected"] == 30 and browser["stats"]["unexpected"] == 0
assert browser["stats"].get("flaky", 0) == 0
coverage = read_json(EVIDENCE / "backend-coverage.json")
front_coverage = read_json(EVIDENCE / "frontend-coverage/coverage-summary.json")["total"]
performance = read_json(EVIDENCE / "local-performance.json")
front_audit = read_json(EVIDENCE / "frontend-audit-final.json")
back_audit = read_json(EVIDENCE / "backend-audit-after.json")
assert not any(front_audit["metadata"]["vulnerabilities"].values())
assert not any(d["vulns"] for d in back_audit["dependencies"])
baseline = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
node_version = subprocess.check_output(["node", "--version"], text=True).strip()
summary = {
    "date": "2026-11-17", "base_commit": baseline, "branch": branch,
    "working_tree_modified": True, "backend_iterations": [{k: v for k, v in r.items() if k != "cases"} for r in backend],
    "frontend_iterations": [{k: v for k, v in r.items() if k != "cases"} for r in frontend],
    "browser": browser["stats"], "backend_coverage": coverage["totals"],
    "frontend_coverage": front_coverage, "frontend_audit_findings": 0, "backend_audit_findings": 0,
    "python": platform.python_version(), "node": node_version,
}
(EVIDENCE / "evaluation-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="ReportTitle", fontName="Helvetica-Bold", fontSize=27, leading=32, textColor=colors.black, spaceAfter=17))
styles.add(ParagraphStyle(name="ReportHeading", fontName="Helvetica-Bold", fontSize=16, leading=21, textColor=colors.black, spaceBefore=12, spaceAfter=11))
styles.add(ParagraphStyle(name="ReportSub", fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=colors.black, spaceBefore=10, spaceAfter=5))
styles.add(ParagraphStyle(name="ReportBody", fontName="Helvetica", fontSize=10, leading=14.2, textColor=colors.HexColor("#24353d"), spaceAfter=9, alignment=TA_LEFT))
styles.add(ParagraphStyle(name="ReportSmall", parent=styles["ReportBody"], fontSize=8.3, leading=11.2, spaceAfter=5))
styles.add(ParagraphStyle(name="ReportCode", fontName="Courier", fontSize=7.7, leading=11, spaceAfter=8, wordWrap="CJK"))
story, markdown = [], []


def p(text, small=False):
    story.append(Paragraph(escape(text), styles["ReportSmall" if small else "ReportBody"]))
    markdown.append(text + "\n")


def h(text, sub=False):
    story.append(Paragraph(escape(text), styles["ReportSub" if sub else "ReportHeading"]))
    markdown.append(("### " if sub else "## ") + text + "\n")


def table(headers, rows, widths):
    data = [[Paragraph(escape(str(v)), styles["ReportSmall"]) for v in row] for row in [headers] + rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4efed")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, 0), .7, colors.HexColor("#9fb9b4")),
        ("LINEBELOW", (0, 1), (-1, -1), .3, colors.HexColor("#dce3e5")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9f9")]),
    ]))
    story.extend([t, Spacer(1, 10)])
    markdown.extend(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"])
    markdown.extend("| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in rows)
    markdown.append("")


def page():
    story.append(PageBreak())


story.append(Paragraph("TelemetryX Software Testing and Evaluation Report", styles["ReportTitle"]))
markdown.append("# TelemetryX Software Testing and Evaluation Report\n")
p("Engineering evaluation for academic project review | 17 November 2026")
p("TelemetryX combines an industrial monitoring workspace with a separate C-MAPSS research cockpit. This report presents the executed tests, reproduced defects, corrective changes and repeat verification, so a project guide can assess both the implementation and the evidence supporting it.")
h("Evaluation outcome")
p("The final recorded checks passed: 64 backend cases in each of three post-fix runs, 29 frontend component cases in each of three final runs, and 30 production-browser executions. Both final dependency scans reported zero known findings. Testing reproduced and corrected input-validation, validation-response, text-contrast and sidebar-access problems.")
table(["Verification layer", "Recorded final result"], [
    ["Backend unit and integration", "64 / 64 passed per run; three post-fix runs"],
    ["Frontend components", "29 / 29 passed per run; three final runs"],
    ["Production browser workflows", "30 / 30 passed; five scenarios x three configurations x two iterations"],
    ["Dependency scanning", "Zero reported findings in both final scans"],
], [187, 316])
h("How to interpret the outcome")
p("These results support a working local evaluation demonstration within the tested scope. They do not prove that the software is error-free, establish production capacity, or validate predictive accuracy on real industrial equipment. Coverage gaps and unexecuted deployment checks are listed explicitly on page 8.")
h("Tested revision and environment")
p(f"Base commit {baseline} on {branch}, plus the local cleanup, fixes and evaluation changes. The tested working tree is modified and has not been committed or pushed. A source hash manifest accompanies the evidence.", small=True)
p(f"Windows host; Python {platform.python_version()}; Node.js {node_version}; Next.js 15.5.29; Vitest 5.1.0; Playwright 1.65.1. Backend tests use temporary SQLite databases. Browser tests use ports 3001 and 8001, disposable storage and a separate optimized Next.js build.", small=True)

page()
h("Test strategy and execution iterations")
p("The campaign began with the existing suites, added adversarial cases, reproduced failures, implemented focused fixes, and repeated full regression checks. A passing retry was not used to conceal a failed case; intermediate results remain in the evidence folder.")
table(["Stage", "Evidence and interpretation"], [
    ["Initial baseline", "45 existing backend cases passed; combined coverage 87%. Existing component baseline contained 21 cases."],
    ["New adversarial probes", "18 cases: 15 failed and 3 passed before fixes; the same 18 passed after fixes. Multiple failures represent repeated forms of a few underlying defects."],
    ["Browser discovery", "Early runs exposed contrast failures and an unreachable sign-out control. Some timeouts were test-selector assumptions, launch-path issues or development-toolbar interference, not product defects."],
    ["Expanded regression", "64 backend cases passed in each of three post-fix runs. Run 1 preceded dependency remediation; runs 2 and 3 used the patched Python environment."],
    ["Final verification", "29 component cases passed three times. Production-browser verification repeated every scenario twice for Chromium desktop, Firefox desktop and mobile Chromium, without automatic retries."],
], [119, 384])
h("Coverage of test types")
table(["Test type", "Executed scope"], [
    ["Functional and integration", "Identity, companies, assets, sensors, imports, alerts, maintenance, models, predictions and background jobs"],
    ["Negative and boundary", "Malformed inputs, whitespace-only values, non-finite numbers, limits, upload errors, incompatible or stale predictive inputs"],
    ["Security and isolation", "Company boundaries, roles, sessions, hostile origins, credential revocation, login throttling and dependency scanning"],
    ["Compatibility and usability", "Chromium and Firefox desktop, emulated mobile viewport, keyboard focus, responsive width and sidebar reachability"],
    ["Quality and reliability", "Python lint/format/type checks, strict TypeScript, production build, migrations, retries, recovery and repeated runs"],
], [119, 384])
p("Browser emulation checks a mobile layout and browser profile; it is not a test on a physical Android device. Automated axe checks cover selected rendered states and WCAG rule tags, not a complete accessibility certification.", small=True)
p("Sandbox file-access restrictions also interrupted initial test and typing commands. They were rerun with access to isolated temporary files and dependency stubs. These environment failures are excluded from application defect counts.", small=True)

page()
h("Backend defects and corrective analysis")
h("F01 Required fields accepted blank descriptions", True)
p("Reproduction: submit a registration with a name or company_name containing only spaces, or pass whitespace-only site names, sensor names/units and work titles. Minimum-length validation accepted the original strings; registration then stripped them after validation, allowing an empty stored identity. The result was blank workspace labels and incomplete asset or maintenance records.")
p("Correction: normalize request text before field constraints through a shared input model. Passwords are excluded because their whitespace is significant. Regression cases cover rejected blanks and valid surrounding whitespace, including proof that passwords remain unchanged. Severity: medium, based on data-integrity impact.")
h("F02 Email syntax checks were too permissive", True)
p("Reproduction: a@@example.com, a b@example.com, @example.com and a@example..com passed the previous check, which only looked for an at-sign and a dot in the domain. Such identifiers could produce unusable identity and invitation records.")
p("Correction: apply a stricter practical email syntax check after trimming and lowercasing. The registration and invitation paths share this validation. Negative tests reject the malformed examples and retain normalization for an otherwise valid address. Severity: medium. Syntax validation does not prove address ownership or deliverability; email verification remains outside the pilot.")
h("F03 Non finite values caused a server error", True)
p("Reproduction: send raw telemetry JSON containing NaN, Infinity, -Infinity or an overflowing numeric literal. The sensor schema correctly rejected the value, but FastAPI's error details retained the non-finite raw input. JSON error-response serialization then failed, turning an invalid request into a server error.")
p("Correction: a request-validation handler emits only the error type, location and message. Raw inputs and exception context are excluded, producing a valid HTTP 422 response and avoiding accidental credential echoing. All four numeric cases now return parseable JSON. Severity: medium, based on request robustness and diagnostic failure.")
h("Migration configuration maintenance", True)
p("Alembic reported deprecated path splitting for prepend_sys_path. Adding path_separator = os makes the intended behavior explicit. The final migration-preservation tests pass after this change. This was a maintenance warning rather than a failed schema migration.")

page()
h("Frontend and dependency findings")
h("F04 Secondary text had insufficient contrast", True)
p("Axe found low-contrast sign-in helper text, inactive tabs, breadcrumbs and research metadata. Examples on the sign-in screen measured approximately 2.5:1 to 4.0:1 against a 4.5:1 normal-text requirement. Repetition after the sample pipeline also exposed a low-contrast rose-colored risk value that was absent from the empty state.")
p("Correction: darken text on light surfaces, retain readable status colors, and adjust the sidebar label on its dark background. Final scans of authentication, industrial overview and research overview reported no violations for the selected WCAG 2 A/AA and 2.1 AA rule tags in all tested configurations. Severity: medium, based on readability and accessibility impact.")
h("F05 Sign out was unreachable on a short viewport", True)
p("At the desktop test viewport of 1280 x 720, the fixed sidebar's combined contents extended below the visible screen. The sign-out button existed in the DOM but could not be reached by scrolling the page. The browser test reproduced the resulting inability to sign out through that control.")
p("Correction: enable vertical scrolling inside the sidebar. The final workflow creates data, reloads the page, uses the sign-out button and confirms that the session endpoint returns HTTP 401 afterward. It passes on desktop Chromium, desktop Firefox and mobile Chromium. Severity: medium, based on user-session control.")
h("F06 Dependency audit findings", True)
p("The initial npm audit reported 28 findings: 4 critical, 6 high, 17 moderate and 1 low. The initial Python scan reported 24 advisory entries across 5 packages; advisory aliases can overlap, so this is not a count of independent exploitable defects. Scanners identify affected package versions; exploitation was not attempted.")
p("Correction: update Next.js from 15.5.25 to 15.5.29, update Vitest/Vite and their React plugin, and apply patched PostCSS/source-map dependencies. On Python, remove unused FastAPI CLI/cloud extras, keep explicit ASGI and multipart dependencies, and update certifi, PyJWT and pytest. Both final scans report zero known findings. The Next.js image-optimization advisory is condition-dependent, including glibc-based Linux; it was an audit finding, not a reproduced Windows exploit.")
h("Supporting corrections", True)
p("Updated the README's obsolete claim that equipment RUL models were unavailable, replaced a deprecated testing-helper release, and made the Vitest configuration explicitly ESM. Windows launch paths, ambiguous selectors and development-overlay interference were corrected in the test harness and are not counted as application defects.", small=True)

page()
h("Final verification and coverage analysis")
b = coverage["totals"]
line_pct = 100 * b["covered_lines"] / b["num_statements"]
branch_pct = 100 * b["covered_branches"] / b["num_branches"]
table(["Measure", "Observed result", "Meaning"], [
    ["Backend line coverage", f"{line_pct:.2f}%", f"{b['covered_lines']} of {b['num_statements']} executable statements reached"],
    ["Backend branch coverage", f"{branch_pct:.2f}%", f"{b['covered_branches']} of {b['num_branches']} branch outcomes reached"],
    ["Backend combined coverage", f"{b['percent_covered']:.2f}%", "coverage.py combined line and branch denominator"],
    ["Frontend line coverage", f"{front_coverage['lines']['pct']:.2f}%", "Vitest component instrumentation; browser runs are separate"],
    ["Frontend statement coverage", f"{front_coverage['statements']['pct']:.2f}%", "473 of 774 statements reached in the recorded component run"],
    ["Frontend branch coverage", f"{front_coverage['branches']['pct']:.2f}%", "403 of 778 branch outcomes reached"],
], [147, 91, 265])
p("Coverage describes what the instrumented suites executed; it is not a probability of correctness. The backend combined figure rounds to 88%. The frontend suite reaches substantially more of the industrial workspace than the research page. Layout entry points and less-used research branches remain lightly covered by component tests, although production browser workflows execute both routes.")
h("Verified behavior by subsystem")
table(["Subsystem", "Representative assertions"], [
    ["Identity and tenancy", "Sign-in/out, session revocation, origin rejection, workspace isolation, role restrictions and last-admin protection"],
    ["Telemetry and maintenance", "Source checksums, deduplication, invalid units/ranges, stale data, sustained alerts, valid assignees and required completion findings"],
    ["Research and equipment ML", "Engine/run holdouts, train-only preprocessing, immutable source snapshots, model compatibility, intervals and stale/out-of-range inference rejection"],
    ["Jobs and persistence", "Idempotency, failure/retry/cancel, bounded transient retries, worker recovery interfaces and migration row preservation"],
    ["Build and static checks", "Ruff check/format, mypy for app, strict TypeScript with unused declarations, optimized Next.js build and Git whitespace checks"],
], [119, 384])
p("The repeat runs kept the same acceptance criteria. Browser automatic retries were disabled; all 30 final executions passed without relying on retry-based recovery. Unit/component cases are counted separately from the five browser scenario definitions.", small=True)

page()
h("Performance and local scalability observations")
p("The performance case uses FastAPI TestClient and temporary SQLite, not an external network or a production server. It imports four batches, then runs three read rounds with five concurrent callers and twenty summary requests per round. The table reflects the last recorded backend run; times include local Python, SQLAlchemy and SQLite overhead.")
table(["Readings per batch", "Observed time in milliseconds", "Acceptance result"], [
    [r["readings"], r["milliseconds"], "All submitted readings accepted"] for r in performance["ingestion"]
], [125, 181, 197])
table(["Read round", "Median ms", "P95 ms", "Requests per second", "Errors"], [
    [r["iteration"], r["median_ms"], r["p95_ms"], r["requests_per_second"], r["errors"]] for r in performance["summary_reads"]
], [81, 91, 81, 149, 101])
h("What the measurements show", True)
p("The tested ingestion sizes completed successfully, and sixty concurrent summary reads completed without HTTP failures or incorrect machine counts. Larger batches take more time because ingestion performs per-reading lookup and persistence work. This identifies batching/database-query optimization as a useful target before scaling to much larger telemetry volumes.")
h("What the measurements cannot establish", True)
p("These small samples do not locate a saturation point, measure production network latency or establish an availability target. The reported P95 is the nearest-rank 19th observation among twenty requests, so it is sensitive to individual timings. Coverage instrumentation and other local processes can affect the measurements.")
p("No production-scale stress, multi-hour soak, destructive fault injection, distributed-write concurrency or real Redis/PostgreSQL capacity test was performed. The pilot's maximum import contract is not a demonstrated sustained throughput guarantee.")
h("Predictive model evaluation boundary", True)
p("Research workflow tests use the repository's synthetic C-MAPSS-shaped fixtures. Equipment-training tests use controlled labelled fixtures and assert validation/inference contracts. They verify software behavior and data separation, not real-machine reliability, NASA benchmark accuracy or suitability for maintenance decisions.")

page()
h("Browser evidence and demonstration acceptance")
p("The final browser suite used the optimized Next.js frontend with a migrated disposable API. Chromium and Firefox used desktop profiles; the mobile configuration used Pixel 7 emulation. Each scenario ran twice in each configuration, producing thirty passing executions.")
image_path = EVIDENCE / "workspace-chromium-desktop.png"
if image_path.exists():
    shot = Image(str(image_path))
    shot._restrictSize(503, 252)
    story.extend([shot, Spacer(1, 8)])
    p("Recorded industrial overview after equipment, telemetry and work-order creation. Screenshots and machine-readable results are retained with the evidence.", small=True)
table(["Scenario", "Acceptance demonstrated"], [
    ["Authentication and keyboard", "Registration page renders, keyboard focus advances, viewport width fits and selected accessibility checks pass"],
    ["Rejected login", "Invalid credentials produce the expected message and the form remains usable"],
    ["Industrial workflow", "Create account/site/machine/sensor, import CSV, verify an alert, create work, reload session and sign out"],
    ["Research rendering", "Research overview renders in empty or populated state, with selected accessibility and width assertions"],
    ["Sample ML pipeline", "Import/preparation, training and prediction jobs finish; model and finite interval-ordered predictions are available"],
], [119, 384])
p("The first rendering and industrial workflow scenarios also assert absence of uncaught page-level JavaScript exceptions. Backend tests separately exercise alert acknowledgement, recovery and the complete work-order transition rules. A browser workflow pass is not a claim that every button or role permutation was exercised in the browser.", small=True)

page()
h("Limitations and reproducibility")
p("No reproduced application defect remains open from this campaign's final acceptance checks. That conclusion is limited to the recorded test scope. The following items remain relevant for project review and deployment planning.")
table(["Area", "Remaining limitation or next verification"], [
    ["Coverage", "Frontend component coverage remains incomplete; prioritize research-page branches and failure-path interactions. Backend uncovered branches include less common error and deployment paths."],
    ["Deployment", "Docker was unavailable. Real PostgreSQL/Redis integration, Linux containers, reverse-proxy/TLS behavior and multi-worker operation were not executed."],
    ["Accessibility and compatibility", "No Safari/WebKit run, physical-device test or full screen-reader audit. Automated axe findings do not constitute complete WCAG conformance."],
    ["Security", "Zero known dependency findings at scan time is not a penetration-test certificate. SSO/MFA, email verification, account recovery and deployment hardening remain outside this pilot."],
    ["Test tooling", "The final backend run retains upstream Starlette/httpx and AnyIO/pytest deprecation warnings. These are recorded warnings, not failed assertions; no warning filters conceal them."],
], [109, 394])
h("Repeat the checks", True)
commands = [
    "Backend directory: uv sync --all-groups",
    "uv run pytest --cov=app --cov-branch -p no:cacheprovider",
    "uv run ruff check .; uv run ruff format --check .; uv run mypy app",
    "Frontend directory: corepack pnpm install --frozen-lockfile",
    "corepack pnpm test; corepack pnpm typecheck; corepack pnpm build",
    "corepack pnpm exec playwright install chromium firefox",
    "corepack pnpm test:e2e --repeat-each=2",
]
for command in commands:
    story.append(Paragraph(escape(command), styles["ReportCode"]))
markdown.append("```powershell\n" + "\n".join(commands) + "\n```\n")
p("The browser configuration currently contains Windows launch paths. Use free ports 3001/8001 and Node.js 22.12 or newer. It creates its own temporary database/storage and .next-evaluation build; it does not use the development database. The report generator requires the isolated ReportLab/PyMuPDF tooling under tmp/report-packages.", small=True)
h("Evidence and references", True)
p("output/testing/evidence contains JUnit results, browser JSON and HTML reports, coverage summaries, scan output, local-performance.json and evaluation-summary.json. source-manifest.json records SHA-256 values for reviewed application, configuration, test and script files. Re-running commands can replace generated evidence; archive this folder before a new evaluation.", small=True)
p("Dependency remediation references: https://github.com/advisories/GHSA-2464-fhr4-w9xw and https://vitest.dev/guide/migration/. Scanner outputs provide the other advisory identifiers and package versions. Project README.md, docs/industrial-pilot.md and docs/cmapss-provenance.md define workflow and prediction boundaries.", small=True)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#52656d"))
    canvas.drawString(46, A4[1] - 28, "TelemetryX  |  Software evaluation  |  17 November 2026")
    canvas.drawString(46, 25, "Tested scope and evidence are stated explicitly")
    canvas.drawRightString(A4[0] - 46, 25, str(doc.page))
    canvas.restoreState()


OUTPUT.parent.mkdir(parents=True, exist_ok=True)
SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=46, leftMargin=46, topMargin=52, bottomMargin=47, title="TelemetryX Software Testing and Evaluation Report", author="TelemetryX Project").build(story, onFirstPage=footer, onLaterPages=footer)
(ROOT / "docs/testing-evaluation-report.md").write_text("\n".join(markdown), encoding="utf-8")
paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
manifest = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(set(paths)) if (ROOT / name).is_file() and name.startswith(("backend/", "frontend/", "scripts/")) and not name.startswith("backend/output/")}
(EVIDENCE / "source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

import pymupdf as fitz

pdf = fitz.open(str(OUTPUT))
qa = ROOT / "tmp/pdfs/testing-report"
qa.mkdir(parents=True, exist_ok=True)
pages = []
for number, document_page in enumerate(pdf, start=1):
    document_page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4)).save(str(qa / f"page-{number}.png"))
    pages.append({"page": number, "characters": len(document_page.get_text()), "width": document_page.rect.width, "height": document_page.rect.height})
(qa / "pages.json").write_text(json.dumps(pages, indent=2), encoding="utf-8")
print(json.dumps({"pdf": str(OUTPUT), "pages": len(pdf), "summary": str(EVIDENCE / "evaluation-summary.json")}))
