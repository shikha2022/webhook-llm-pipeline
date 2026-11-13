"""Automated tests. Run from the project folder with:  pytest -v

They force mock mode and use a temporary folder, so they never call a paid API,
touch S3, or write to your real ./data folder.
"""
import hashlib
import hmac
import json

import pytest

import app as app_module
from summarize import check_event

SECRET = "test-secret"

GOOD_EVENT = {
    "event_id": "evt_test_1",
    "event_type": "install_attributed",
    "app": "demo-app",
    "partner": "example-network",
    "campaign": "winter_sale_ctv",
    "platform": "CTV",
    "country": "IN",
    "revenue": 0,
    "timestamp": "2026-11-11T09:30:00Z",
}


def sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                       # raw events go to a temp ./data
    monkeypatch.setenv("LLM_PROVIDER", "mock")        # never call the paid API
    monkeypatch.delenv("S3_BUCKET", raising=False)    # never touch S3
    monkeypatch.setattr(app_module, "SECRET", SECRET)
    monkeypatch.setattr(app_module, "SEEN_FILE", tmp_path / "data" / "seen_events.json")
    return app_module.app.test_client()


def post(client, payload, signature="valid"):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if signature == "valid":
        headers["X-Signature"] = sign(body)
    elif signature is not None:
        headers["X-Signature"] = signature
    return client.post("/webhook", data=body, headers=headers)


# ---- rule checks ---------------------------------------------------------

def test_clean_event_has_no_problems():
    assert check_event(GOOD_EVENT) == []


def test_missing_country_is_flagged():
    event = {k: v for k, v in GOOD_EVENT.items() if k != "country"}
    assert "missing field 'country'" in check_event(event)


def test_negative_revenue_is_flagged():
    problems = check_event({**GOOD_EVENT, "revenue": -5, "currency": "USD"})
    assert any("negative revenue" in p for p in problems)


def test_revenue_without_currency_is_flagged():
    problems = check_event({**GOOD_EVENT, "revenue": 2})
    assert "revenue is set but 'currency' is missing" in problems


def test_zero_revenue_needs_no_currency():
    assert check_event({**GOOD_EVENT, "revenue": 0}) == []


# ---- webhook behaviour ---------------------------------------------------

def test_valid_event_is_stored_and_summarised(client, tmp_path):
    r = post(client, GOOD_EVENT)
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok"
    assert body["summary"].startswith("[mock]")
    assert (tmp_path / "data" / "events").exists()


def test_bad_signature_is_rejected(client):
    assert post(client, GOOD_EVENT, signature="wrong").status_code == 401


def test_missing_signature_is_rejected(client):
    assert post(client, GOOD_EVENT, signature=None).status_code == 401


def test_body_that_is_not_json_is_rejected(client):
    body = b"not json"
    r = client.post("/webhook", data=body,
                    headers={"Content-Type": "application/json", "X-Signature": sign(body)})
    assert r.status_code == 400


def test_json_list_instead_of_object_is_rejected(client):
    body = b"[1, 2, 3]"
    r = client.post("/webhook", data=body,
                    headers={"Content-Type": "application/json", "X-Signature": sign(body)})
    assert r.status_code == 400


def test_duplicate_event_is_ignored(client):
    first = post(client, GOOD_EVENT).get_json()
    second = post(client, GOOD_EVENT).get_json()
    assert first["status"] == "ok"
    assert second["status"] == "duplicate"


def test_llm_failure_still_returns_200_and_keeps_event(client, monkeypatch, tmp_path):
    def boom(_payload):
        raise RuntimeError("model is down")

    monkeypatch.setattr(app_module, "summarize", boom)
    r = post(client, {**GOOD_EVENT, "event_id": "evt_llm_down"})
    assert r.status_code == 200                      # sender must not retry
    body = r.get_json()
    assert body["summary"] is None
    assert (tmp_path / "data" / "events").exists()   # raw event was still saved


def test_health_endpoint(client):
    assert client.get("/health").get_json() == {"status": "ok"}
