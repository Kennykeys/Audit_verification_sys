from copy import deepcopy

from fastapi.testclient import TestClient

from backend import main
from backend.integrity import migrate_legacy_ledger
from backend.services.audit_service import AuditService


class StubRepository:
    def __init__(self, entries):
        self.entries = entries

    def load_entries(self):
        return deepcopy(self.entries)

    def append_entry(self, entry):
        return entry


def linked_entries():
    legacy = [{"transaction_id": "TX-1", "amount": 10, "member_id": "M001", "description": "One", "created_at": "2026-09-19T12:00:00Z", "method": "Admin", "network": None, "phone_number": None}, {"transaction_id": "TX-2", "amount": 20, "member_id": "M002", "description": "Two", "created_at": "2026-09-19T12:01:00Z", "method": "Admin", "network": None, "phone_number": None}]
    return migrate_legacy_ledger(legacy)


def client_for(monkeypatch, entries):
    service = AuditService(StubRepository(entries))
    monkeypatch.setattr(main, "get_audit_service", lambda: service)
    return TestClient(main.app)


def test_integrity_endpoint_returns_valid_ledger(monkeypatch):
    entries = linked_entries()
    response = client_for(monkeypatch, entries).get("/integrity")
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["entries_checked"] == 2
    assert response.json()["ledger_head_hash"] == entries[-1]["entry_hash"]


def test_integrity_endpoint_reports_first_invalid_entry(monkeypatch):
    entries = linked_entries()
    entries[1]["amount"] = 21
    response = client_for(monkeypatch, entries).get("/integrity")
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["first_invalid_entry"]["failure_type"] == "entry_hash"


def test_verify_endpoint_includes_record_and_context_validity(monkeypatch):
    entries = linked_entries()
    entries[1]["amount"] = 21
    response = client_for(monkeypatch, entries).get("/verify/TX-1")
    assert response.status_code == 200
    assert response.json()["record_valid"] is True
    assert response.json()["ledger_context_valid"] is False
    assert response.json()["verified"] is False


def test_openapi_exposes_integrity_response_schema():
    schema = main.app.openapi()
    response_schema = schema["paths"]["/integrity"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("LedgerIntegrityResult")


def test_integrity_endpoint_accepts_empty_ledger(monkeypatch):
    response = client_for(monkeypatch, []).get("/integrity")
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["entries_checked"] == 0
    assert response.json()["ledger_head_hash"] is None


def test_integrity_endpoint_detects_deleted_entry(monkeypatch):
    entries = linked_entries()
    del entries[0]
    response = client_for(monkeypatch, entries).get("/integrity")
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["first_invalid_entry"]["failure_type"] == "sequence"


def test_integrity_endpoint_detects_reordered_entries(monkeypatch):
    entries = linked_entries()
    entries[0], entries[1] = entries[1], entries[0]
    response = client_for(monkeypatch, entries).get("/integrity")
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["first_invalid_entry"]["failure_type"] == "sequence"


def test_integrity_endpoint_detects_malformed_ledger(monkeypatch):
    response = client_for(monkeypatch, {"not": "a list"}).get("/integrity")
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["first_invalid_entry"]["failure_type"] == "malformed_ledger"
