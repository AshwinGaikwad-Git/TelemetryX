# TelemetryX industrial pilot

## Implemented scope

The industrial entry point is `/`. The synthetic research cockpit remains at `/demo`. Industrial records live in separate `industrial_*` tables. Research models, job payloads and telemetry never become industrial machine predictions implicitly.

This release implements the foundation, monitoring and a basic maintenance workflow. It is an HTTP/CSV pilot, not a connected SCADA system or a validated predictive-maintenance deployment. No artificial machinery data is inserted into company workspaces.

## First-time workflow

1. Start the backend and frontend using README.md. Apply Alembic migrations before starting the API. For the known legacy SQLite database, `uv run python -m scripts.migrate_local` verifies the old schema where needed, backs it up and upgrades without deleting historical records.
2. Open `http://localhost:3000`. Create an account with your name, email, a password of at least 12 characters, and your company name. No default accounts/passwords exist.
3. In Machinery, register a site (IANA timezone, e.g. `Asia/Kolkata`), then a machine. Its asset tag is unique within the company. Record category, manufacturer/model, production area, criticality, operating state and maintenance context.
4. Select the machine and register sensors. A sensor key is unique within that machine. Set the exact unit, expected reporting interval, valid measurement range, warning thresholds and number of consecutive samples required for an alert.
5. In Data connections, import timestamped CSV or use an ingestion key from Team & access. Review accepted/duplicate/rejected rows and the source checksum.
6. Review Machinery and Operations overview. Freshness and operating state are separate from condition. The interface refreshes every 15 seconds while the page is visible. Displayed timestamps use the browser timezone; the site timezone is stored as metadata.
7. Acknowledge a sustained-threshold alert, create a linked inspection work order, assign a member, start work, record findings/component/downtime, complete it, then have an authorized planner verify completion.

## Company and permission boundaries

Each request checks the current session and membership in the company named in the route. IDs from another company do not bypass this check. Site/machine/sensor/reading references have composite company foreign keys. SQLite foreign-key enforcement is enabled for runtime and test connections. Source imports are stored under `RAW_STORAGE_PATH/industrial/{company_id}/{checksum}`.

| Role | Capabilities |
|---|---|
| Admin | Company membership, invitations and roles; all operational actions; integration credentials |
| Manager | Sites/machines, imports, alert review, maintenance planning and verification, audit history |
| Engineer | Manager operations plus sensor configuration and integration credentials |
| Technician | Read the workspace, acknowledge alerts, start/complete work assigned to them |
| Viewer | Read machinery, sensor data, alerts, work orders and member directory |

An administrator can create a private one-time invitation tied to an email/role. It expires after 48 hours; the invited account must sign in with that email and submit the token. No email is sent automatically. Invitation tokens are stored hashed. Removing a member immediately removes company access, invalidates their outstanding company invitations and returns assigned/in-progress work to the open planning queue. Historical user/work records remain. A company must retain an administrator. Other company memberships remain valid.

Browser sessions use random 256-bit tokens stored only as SHA-256 hashes in the database, with an HttpOnly SameSite=Lax cookie and seven-day expiration. Passwords use salted scrypt. Sign-out invalidates the server-side token. Mutating industrial requests with an unapproved Origin are rejected, and credentialed CORS uses explicit origins. No session or integration secret is stored in localStorage.

Set `ENVIRONMENT=production` behind HTTPS to enable Secure cookies and disable legacy demo API routes. Industrial browser requests use the website-relative `/api/v1/industrial` path. Next.js forwards them to `TELEMETRYX_API_URL` (set before `next build` for production, or before starting the development server) (default `http://127.0.0.1:8000`; Compose uses `http://api:8000`). Configure `API_CORS_ORIGINS` to include the actual website origin. The legacy demo still uses `NEXT_PUBLIC_API_BASE_URL`. The localhost defaults are for development. The in-memory sign-in limiter is a pilot safeguard (30 attempts per IP per 15 minutes); multi-process production needs a shared gateway limiter. SSO/MFA, verified email, password recovery, session management, compliance review and production hardening are not implemented. Do not treat this branch as a completed public SaaS deployment.

## Telemetry contract

JSON endpoint: `POST /api/v1/industrial/companies/{company_id}/telemetry`.

Use a signed-in admin/manager/engineer session or `X-Ingestion-Key: <secret>`. Keys are company-scoped, ingestion-only, shown once at creation and revocable. They cannot read telemetry or change assets.

```json
{
  "readings": [
    {
      "machine_id": "<registered machine UUID>",
      "sensor_key": "bearing_temperature",
      "timestamp": "2026-11-13T09:30:00Z",
      "value": 62.4,
      "unit": "degC"
    }
  ]
}
```

CSV endpoint: `POST /api/v1/industrial/companies/{company_id}/machines/{machine_id}/imports`, multipart `file`. The exact headers are `sensor_key,timestamp,value,unit`; UTF-8 BOM is accepted. The UI can download a template. Replace its placeholder with actual measurements before import.

Rules:

- Maximum 10,000 readings per request/import and `MAX_UPLOAD_SIZE_MB` bytes for CSV (also checked on normalized API batches).
- Explicit timestamp timezone, finite numeric value, registered machine/sensor, exact unit and configured valid range are required. Unit conversion is not performed.
- Timestamps more than five minutes in the future are rejected. Out-of-order historical points are accepted and sorted for display, without inventing a current connection.
- Matching sensor/timestamp/value is a duplicate; conflicting values are rejected. Existing readings are never overwritten.
- Malformed CSV or invalid typed rows reject the file before ingestion. Semantically invalid rows (unknown sensor, wrong unit, measurement range, timestamp conflict) receive row errors while valid rows are accepted.
- CSV source bytes are retained exactly. API batches retain the normalized validated JSON. Source hashes and import outcomes appear in the audit trail. Filenames never select storage paths.
- Industrial ingestion currently executes synchronously with bounded batch size. The existing persisted job system remains specific to the research subsystem; tenant-scoped bulk queues are future work.

## Freshness, condition and alerts

A signal is fresh until three expected reporting intervals have elapsed. A machine is `not_connected` without observations, `offline` when all signals are stale, `partial` with mixed signal freshness, and `online` when all configured signals are fresh.

Condition is `attention` when any fresh signal breaches a warning limit, `unknown` if coverage is incomplete or no limits are configured, `insufficient_data` until configured channels have enough samples, and `within_limits` otherwise. It is not a calibrated health score or failure probability. Freshness/condition are recalculated when the dashboard reads data.

An alert opens only after the configured number of consecutive fresh observations breach the same side of a limit. Large gaps break persistence. Repeated breaches do not duplicate an active alert. Acknowledgement records the reviewing user. Consecutive normal readings resolve the alert; stopping telemetry does not silently resolve it. Historical ingestion does not generate stale live alerts. Alert evaluation currently runs on ingestion, not an external streaming engine.

Work transitions are `open -> assigned -> in_progress -> completed -> verified`, with cancellation before completion and an engineering-review return from completed to in-progress. Completion requires findings. Technicians cannot assign, verify or progress another person's work. Downtime is recorded work-order downtime, not independently measured plant availability or OEE; overlapping jobs are not automatically deduplicated.

## API inventory

Auth prefix: `/api/v1/industrial/auth`. Routes: `register`, `login`, `logout`, `me`, `companies` (create), `join` (JSON invitation token).

Workspace prefix: `/api/v1/industrial/companies/{company_id}`.

| Resource | Methods / behavior |
|---|---|
| `/sites` | GET, POST |
| `/machines` | GET (optional site filter), POST |
| `/machines/{id}` | GET, PATCH operating state |
| `/machines/{id}/sensors` | POST sensor definition |
| `/machines/{id}/readings` | GET by sensor_key; start/end/before/limit filters |
| `/machines/{id}/imports` | POST CSV |
| `/telemetry` | POST authenticated JSON batch |
| `/summary` | GET company/site monitoring and work counts |
| `/alerts` | GET; POST `/{id}/acknowledge` |
| `/work-orders` | GET, POST; PATCH `/{id}` lifecycle/findings |
| `/members` | GET; PATCH/DELETE `/{user_id}` access |
| `/invitations` | POST private one-time invitation |
| `/ingestion-keys` | GET, POST; POST `/{id}/revoke` |
| `/audit` | GET latest 200 events, planner roles |

Pilot bounds: 500 machines per scoped registry/summary view, 100 sensors per machine, 500 alert/work rows per view, and up to 5000 readings per history request (500 by default). History supports a `before` timestamp cursor. Summary counts explicitly cover the bounded selected view. There are no fleet-scale capacity claims.

## Next advancement gates

Choose one machinery class and obtain representative real telemetry and maintenance labels. Validate measurement units, operating modes and rule limits with an engineer. Measure false alerts and useful warning time. Only then introduce equipment-specific anomaly/failure/RUL models. Hardware gateways (MQTT/OPC UA/Modbus), tenant-scoped bulk jobs, editable/versioned sensor configurations, documents/schedules, notification delivery, deployment automation and higher-volume time-series storage remain future work.
