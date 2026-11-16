"""Adversarial input and identity regressions for the evaluation campaign."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.industrial.schemas import Credentials, Registration, SensorCreate, SiteCreate, WorkCreate
from app.main import app


@pytest.mark.parametrize("field", ["name", "company_name"])
def test_registration_rejects_blank_identity_fields(field: str) -> None:
    payload = dict(
        name="Owner",
        company_name="Factory",
        email="owner@example.com",
        password="long-password-123",
    )
    payload[field] = "   "
    with TestClient(app) as client:
        assert client.post("/api/v1/industrial/auth/register", json=payload).status_code == 422


@pytest.mark.parametrize(
    "email",
    ["a@@example.com", "a b@example.com", "@example.com", "a@example..com", "a@example.com "],
)
def test_email_validation_rejects_malformed_addresses(email: str) -> None:
    # Leading/trailing whitespace is deliberately normalized for valid addresses.
    if email == "a@example.com ":
        assert Credentials(email=email, password="long-password-123").email == "a@example.com"
    else:
        with pytest.raises(ValidationError):
            Credentials(email=email, password="long-password-123")


@pytest.mark.parametrize(
    "schema,payload",
    [
        (SiteCreate, {"name": "   "}),
        (SensorCreate, {"key": "temp", "name": "   ", "unit": "degC"}),
        (SensorCreate, {"key": "temp", "name": "Temperature", "unit": "   "}),
        (WorkCreate, {"machine_id": "00000000-0000-0000-0000-000000000001", "title": "   "}),
    ],
)
def test_required_descriptions_cannot_be_whitespace(schema, payload) -> None:
    with pytest.raises(ValidationError):
        schema(**payload)


def test_normalization_does_not_change_password() -> None:
    value = Registration(
        name=" Owner ",
        company_name=" Factory ",
        email=" OWNER@EXAMPLE.COM ",
        password=" secret-password-123 ",
    )
    assert value.name == "Owner"
    assert value.company_name == "Factory"
    assert value.password == " secret-password-123 "


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e309"])
def test_nonfinite_request_values_return_validation_error_not_server_error(value: str) -> None:
    content = (
        '{"readings":[{"machine_id":"00000000-0000-0000-0000-000000000001","sensor_key":"temp","timestamp":"2026-11-16T10:00:00Z","value":'
        + value
        + ',"unit":"degC"}]}'
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/industrial/companies/00000000-0000-0000-0000-000000000002/telemetry",
            content=content,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["type"] == "finite_number"
    assert "Internal Server Error" not in response.text
    json.loads(response.text, parse_constant=lambda item: pytest.fail(f"Invalid JSON {item}"))


def test_unknown_account_login_does_not_disclose_registration() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/industrial/auth/login",
            json={"email": "missing@example.com", "password": "long-password-123"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Email or password is incorrect"


def test_login_rate_limit_is_enforced() -> None:
    with TestClient(app) as client:
        for _ in range(30):
            assert (
                client.post(
                    "/api/v1/industrial/auth/login",
                    json={"email": "missing@example.com", "password": "long-password-123"},
                ).status_code
                == 401
            )
        assert (
            client.post(
                "/api/v1/industrial/auth/login",
                json={"email": "missing@example.com", "password": "long-password-123"},
            ).status_code
            == 429
        )
