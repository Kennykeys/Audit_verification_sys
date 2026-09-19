import json
import logging

from fastapi.testclient import TestClient

from backend import main
from backend.observability import StructuredEventLogger
from backend.repository import LedgerCorruptionError
from backend.schemas import EntryIntegrityResult, LedgerIntegrityResult


class HealthyService:
    def verify_ledger(self):
        return LedgerIntegrityResult(
            valid=True,
            total_entries=2,
            entries_checked=2,
            first_invalid_entry=None,
            ledger_head_hash="a" * 64,
        )


class InvalidService:
    def verify_ledger(self):
        return LedgerIntegrityResult(
            valid=False,
            total_entries=2,
            entries_checked=1,
            first_invalid_entry=EntryIntegrityResult(
                sequence=2,
                valid=False,
                failure_type="entry_hash",
            ),
            ledger_head_hash=None,
        )


class UnavailableService:
    def verify_ledger(self):
        raise LedgerCorruptionError("/private/path/audit_log.json is unavailable")


def test_liveness_returns_minimal_process_status_and_request_id():
    response = TestClient(main.app).get(
        "/health/live",
        headers={"X-Request-ID": "health-live-1234"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "live"}
    assert response.headers["x-request-id"] == "health-live-1234"


def test_readiness_reports_ready_without_exposing_ledger_contents(monkeypatch):
    monkeypatch.setattr(main, "get_audit_service", lambda: HealthyService())
    response = TestClient(main.app).get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "ledger_integrity": "valid",
        "entries_checked": 2,
    }
    assert "ledger_head_hash" not in response.text


def test_readiness_fails_safely_for_invalid_ledger(monkeypatch):
    monkeypatch.setattr(main, "get_audit_service", lambda: InvalidService())
    response = TestClient(main.app).get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "ledger_integrity": "invalid",
        "failure_type": "entry_hash",
    }


def test_readiness_fails_safely_without_path_disclosure(monkeypatch):
    monkeypatch.setattr(main, "get_audit_service", lambda: UnavailableService())
    response = TestClient(main.app).get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "ledger_integrity": "unavailable",
    }
    assert "/private/path" not in response.text


def test_structured_event_logger_redacts_sensitive_fields(caplog):
    event_logger = StructuredEventLogger(logging.getLogger("audit-test"))
    with caplog.at_level(logging.INFO, logger="audit-test"):
        event_logger.emit(
            "authentication_failed",
            request_id="request-1234",
            username="operator",
            password="secret",
            authorization="Bearer token",
            transaction={"member_id": "M001", "description": "private"},
        )
    payload = json.loads(caplog.records[-1].message)
    assert payload["password"] == "[REDACTED]"
    assert payload["authorization"] == "[REDACTED]"
    assert payload["transaction"]["member_id"] == "[REDACTED]"
    assert payload["transaction"]["description"] == "[REDACTED]"
    assert "secret" not in caplog.records[-1].message
    assert "Bearer token" not in caplog.records[-1].message
