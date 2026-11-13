import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.industrial.models import Reading, User
from app.main import app
from app.services import job_service

PASSWORD = "a-long-test-password-2026"


def registered(email: str = "owner@example.com") -> tuple[TestClient, dict, str]:
    client = TestClient(app)
    result = client.post(
        "/api/v1/industrial/auth/register",
        json={
            "name": "Plant owner",
            "email": email,
            "password": PASSWORD,
            "company_name": "Pilot Works",
        },
    )
    assert result.status_code == 201, result.text
    profile = result.json()
    base = f"/api/v1/industrial/companies/{profile['companies'][0]['id']}"
    return client, profile, base


def asset(client: TestClient, base: str) -> tuple[dict, dict]:
    result = client.post(f"{base}/sites", json={"name": "Pune", "timezone": "Asia/Kolkata"})
    assert result.status_code == 201, result.text
    site = result.json()
    result = client.post(
        f"{base}/machines",
        json={
            "site_id": site["id"],
            "name": "Cooling pump",
            "asset_tag": "PUMP-001",
            "equipment_type": "Pump",
            "operating_state": "running",
            "criticality": "high",
        },
    )
    assert result.status_code == 201, result.text
    machine = result.json()
    result = client.post(
        f"{base}/machines/{machine['id']}/sensors",
        json={
            "key": "temperature",
            "name": "Bearing temperature",
            "unit": "degC",
            "expected_interval_seconds": 60,
            "warning_high": 80,
            "valid_min": -50,
            "valid_max": 200,
            "persistence_samples": 3,
        },
    )
    assert result.status_code == 201, result.text
    return machine, result.json()


def points(machine: dict, values: list[float], offset: int = 0) -> dict:
    now = datetime.now(UTC) - timedelta(seconds=offset)
    return {
        "readings": [
            {
                "machine_id": machine["id"],
                "sensor_key": "temperature",
                "timestamp": (now - timedelta(seconds=60 * (len(values) - i))).isoformat(),
                "value": value,
                "unit": "degC",
            }
            for i, value in enumerate(values)
        ]
    }


def invited(owner: TestClient, base: str, role: str) -> tuple[TestClient, dict]:
    email = f"{role}-{uuid.uuid4().hex[:5]}@example.com"
    result = owner.post(f"{base}/invitations", json={"email": email, "role": role})
    assert result.status_code == 201, result.text
    token = result.json()["token"]
    client, profile, _ = registered(email)
    response = client.post("/api/v1/industrial/auth/join", json={"token": token})
    assert response.status_code == 200, response.text
    return client, profile


def test_identity_session_origin_and_logout() -> None:
    client, profile, base = registered()
    assert client.get("/api/v1/industrial/auth/me").json()["id"] == profile["id"]
    cookie = client.cookies.get("telemetryx_session")
    with job_service.SessionLocal() as db:
        user = db.scalars(select(User)).first()
        assert user.password_hash.startswith("scrypt$")
        assert PASSWORD not in user.password_hash
    assert (
        client.post(
            f"{base}/sites",
            json={"name": "Forged"},
            headers={"Origin": "https://untrusted.example"},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/industrial/auth/logout").status_code == 204
    assert client.get("/api/v1/industrial/auth/me").status_code == 401
    client.cookies.set("telemetryx_session", cookie)
    assert client.get("/api/v1/industrial/auth/me").status_code == 401
    assert (
        client.post(
            "/api/v1/industrial/auth/login",
            json={
                "email": "owner@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 200
    )


def test_company_isolation_across_assets_data_and_actions() -> None:
    owner, _, base = registered()
    machine, _ = asset(owner, base)
    outsider, _, other = registered("other@example.com")
    for route in [
        "sites",
        "machines",
        "summary",
        "alerts",
        "work-orders",
        "members",
        "audit",
        f"machines/{machine['id']}",
        f"machines/{machine['id']}/readings?sensor_key=temperature",
    ]:
        assert outsider.get(f"{base}/{route}").status_code == 404
    assert (
        outsider.post(
            f"{other}/machines",
            json={
                "site_id": machine["site_id"],
                "asset_tag": "LEAK",
                "name": "Not owned",
                "equipment_type": "Pump",
            },
        ).status_code
        == 404
    )
    result = outsider.post(f"{other}/telemetry", json=points(machine, [20])).json()
    assert result["accepted"] == 0 and result["rejected"] == 1
    assert (
        outsider.post(
            f"{base}/work-orders",
            json={
                "machine_id": machine["id"],
                "title": "Unauthorized",
            },
        ).status_code
        == 404
    )
    assert outsider.get(f"{other}/machines").json() == []


def test_telemetry_validation_deduplication_and_provenance() -> None:
    client, profile, base = registered()
    machine, _ = asset(client, base)
    payload = points(machine, [30, 31, 32])
    result = client.post(f"{base}/telemetry", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["accepted"] == 3
    assert client.post(f"{base}/telemetry", json=payload).json()["duplicates"] == 3
    payload["readings"][0]["value"] = 99
    assert client.post(f"{base}/telemetry", json=payload).json()["rejected"] == 1
    bad = points(machine, [500, 20])
    bad["readings"][1]["unit"] = "Fahrenheit"
    assert client.post(f"{base}/telemetry", json=bad).json()["rejected"] == 2
    bad = points(machine, [20])
    bad["readings"][0]["timestamp"] = "2026-01-01T10:00:00"
    assert client.post(f"{base}/telemetry", json=bad).status_code == 422
    rows = client.get(
        f"{base}/machines/{machine['id']}/readings?sensor_key=temperature&limit=2"
    ).json()
    assert len(rows) == 2
    assert rows[0]["timestamp"] < rows[1]["timestamp"]
    assert all(row["timestamp"].endswith("Z") for row in rows)
    source = get_settings().raw_storage_path / "industrial" / profile["companies"][0]["id"]
    assert list(source.glob("*.json"))
    events = client.get(f"{base}/audit").json()
    assert any(event["action"] == "telemetry.ingested" for event in events)


def test_stale_or_missing_readings_never_look_healthy() -> None:
    client, _, base = registered()
    machine, _ = asset(client, base)
    snapshot = client.get(f"{base}/machines/{machine['id']}").json()
    assert snapshot["health"] == "unknown"
    assert snapshot["connectivity"] == "not_connected"
    client.post(f"{base}/telemetry", json=points(machine, [100, 100, 100], offset=3600))
    snapshot = client.get(f"{base}/machines/{machine['id']}").json()
    assert snapshot["health"] == "unknown" and snapshot["connectivity"] == "offline"
    assert client.get(f"{base}/alerts").json() == []
    client.post(f"{base}/telemetry", json=points(machine, [25, 25, 25]))
    snapshot = client.get(f"{base}/machines/{machine['id']}").json()
    assert snapshot["health"] == "within_limits" and snapshot["connectivity"] == "online"


def test_alert_persistence_acknowledgement_and_recovery() -> None:
    client, _, base = registered()
    machine, _ = asset(client, base)
    client.post(f"{base}/telemetry", json=points(machine, [90, 91]))
    assert client.get(f"{base}/alerts").json() == []
    client.post(f"{base}/telemetry", json=points(machine, [92, 93, 94]))
    alert = client.get(f"{base}/alerts").json()[0]
    assert alert["status"] == "open" and alert["evidence"]["consecutive_samples"] == 3
    assert (
        client.post(f"{base}/alerts/{alert['id']}/acknowledge").json()["status"] == "acknowledged"
    )
    client.post(f"{base}/telemetry", json=points(machine, [95, 96, 97]))
    assert len(client.get(f"{base}/alerts").json()) == 1
    # Later normal values recover the existing alert without creating another incident.
    newer = points(machine, [40, 40, 40])
    for index, row in enumerate(newer["readings"]):
        row["timestamp"] = (datetime.now(UTC) + timedelta(seconds=index)).isoformat()
    client.post(f"{base}/telemetry", json=newer)
    assert client.get(f"{base}/alerts").json()[0]["status"] == "resolved"


def test_work_order_lifecycle_requires_findings_and_valid_assignee() -> None:
    client, profile, base = registered()
    machine, _ = asset(client, base)
    result = client.post(
        f"{base}/work-orders",
        json={
            "machine_id": machine["id"],
            "title": "Inspect bearing",
            "assigned_to": profile["id"],
        },
    )
    assert result.status_code == 201, result.text
    work = result.json()
    endpoint = f"{base}/work-orders/{work['id']}"
    assert (
        client.patch(endpoint, json={"status": "completed", "findings": "Done"}).status_code == 409
    )
    assert client.patch(endpoint, json={"status": "in_progress"}).status_code == 200
    assert client.patch(endpoint, json={"status": "completed"}).status_code == 400
    assert (
        client.patch(
            endpoint,
            json={
                "status": "completed",
                "findings": "Bearing replaced",
                "component": "bearing",
                "downtime_minutes": 45,
            },
        ).status_code
        == 200
    )
    assert client.patch(endpoint, json={"status": "verified"}).json()["verified_at"]
    assert client.get(f"{base}/summary").json()["recorded_downtime_minutes"] == 45
    assert client.patch(endpoint, json={"status": "in_progress"}).status_code == 409


def test_technician_and_viewer_permissions() -> None:
    owner, _, base = registered()
    machine, _ = asset(owner, base)
    tech, profile = invited(owner, base, "technician")
    viewer, _ = invited(owner, base, "viewer")
    assert tech.post(f"{base}/sites", json={"name": "Blocked"}).status_code == 403
    assert viewer.post(f"{base}/telemetry", json=points(machine, [20])).status_code == 403
    assert viewer.get(f"{base}/machines").status_code == 200
    assert viewer.get(f"{base}/ingestion-keys").status_code == 403
    work = owner.post(
        f"{base}/work-orders",
        json={
            "machine_id": machine["id"],
            "title": "Technician inspection",
            "assigned_to": profile["id"],
        },
    ).json()
    endpoint = f"{base}/work-orders/{work['id']}"
    assert tech.patch(endpoint, json={"status": "in_progress"}).status_code == 200
    assert (
        tech.patch(
            endpoint, json={"status": "completed", "findings": "Checked and cleaned"}
        ).status_code
        == 200
    )
    assert tech.patch(endpoint, json={"status": "verified"}).status_code == 403
    assert owner.patch(endpoint, json={"status": "verified"}).status_code == 200


def test_ingestion_keys_are_company_scoped_ingestion_only_and_revocable() -> None:
    owner, _, base = registered()
    machine, _ = asset(owner, base)
    result = owner.post(f"{base}/ingestion-keys?name=Gateway").json()
    gateway = TestClient(app)
    headers = {"X-Ingestion-Key": result["token"]}
    assert (
        gateway.post(f"{base}/telemetry", json=points(machine, [20]), headers=headers).json()[
            "accepted"
        ]
        == 1
    )
    assert gateway.get(f"{base}/machines", headers=headers).status_code == 401
    other, _, other_base = registered("second@example.com")
    assert (
        gateway.post(
            f"{other_base}/telemetry", json=points(machine, [20]), headers=headers
        ).status_code
        == 401
    )
    listed = owner.get(f"{base}/ingestion-keys").json()[0]
    assert "token" not in listed and "token_hash" not in listed
    owner.post(f"{base}/ingestion-keys/{result['id']}/revoke")
    assert (
        gateway.post(f"{base}/telemetry", json=points(machine, [20]), headers=headers).status_code
        == 401
    )


def test_csv_import_reports_invalid_units_and_preserves_exact_source() -> None:
    client, profile, base = registered()
    machine, _ = asset(client, base)
    timestamp = datetime.now(UTC).isoformat()
    raw = (
        "sensor_key,timestamp,value,unit\r\n"
        f"temperature,{timestamp},30,degC\r\n"
        f"temperature,{timestamp},30,F\r\n"
    ).encode()
    response = client.post(
        f"{base}/machines/{machine['id']}/imports",
        files={"file": ("../../test.csv", raw, "text/csv")},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["accepted"] == 1 and report["rejected"] == 1
    path = (
        get_settings().raw_storage_path
        / "industrial"
        / profile["companies"][0]["id"]
        / f"{report['checksum_sha256']}.csv"
    )
    assert path.read_bytes() == raw
    with job_service.SessionLocal() as db:
        assert len(db.scalars(select(Reading)).all()) == 1


def test_api_rejects_invalid_limits_and_unregistered_access() -> None:
    client, _, base = registered()
    machine, _ = asset(client, base)
    assert (
        client.post(
            f"{base}/machines/{machine['id']}/sensors",
            json={
                "key": "bad",
                "name": "Bad",
                "unit": "degC",
                "valid_min": 100,
                "warning_high": 80,
            },
        ).status_code
        == 422
    )
    assert (
        client.post(f"{base}/sites", json={"name": "Invalid", "timezone": "Not/AZone"}).status_code
        == 422
    )
    assert TestClient(app).get(f"{base}/summary").status_code == 401


def test_access_revocation_and_last_administrator_guard() -> None:
    owner, owner_profile, base = registered()
    machine, _ = asset(owner, base)
    tech, tech_profile = invited(owner, base, "technician")
    order = owner.post(
        f"{base}/work-orders",
        json={
            "machine_id": machine["id"],
            "title": "Assigned inspection",
            "assigned_to": tech_profile["id"],
        },
    ).json()
    assert owner.delete(f"{base}/members/{owner_profile['id']}").status_code == 409
    assert (
        owner.patch(f"{base}/members/{owner_profile['id']}", json={"role": "viewer"}).status_code
        == 409
    )
    assert owner.delete(f"{base}/members/{tech_profile['id']}").status_code == 204
    assert tech.get(f"{base}/machines").status_code == 404
    assert tech.get("/api/v1/industrial/auth/me").status_code == 200
    reopened = owner.get(f"{base}/work-orders").json()[0]
    assert reopened["id"] == order["id"]
    assert reopened["status"] == "open" and reopened["assigned_to"] is None
