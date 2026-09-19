from pathlib import Path

from fastapi.testclient import TestClient

from backend import main
from backend.repository import AuditLedgerRepository


def test_recording_workflow_uses_temporary_ledger(monkeypatch, tmp_path):
    ledger = tmp_path / "audit_log.json"
    ledger.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(main, "AUDIT_FILE", str(ledger))
    client = TestClient(main.app)
    payload = {"transaction_id": "TX-E2E-1", "amount": 2500, "member_id": "M001", "description": "Contract test"}
    response = client.post("/record", json=payload)
    assert response.status_code == 200
    assert response.json()["transaction"]["sequence"] == 1
    assert client.post("/record", json=payload).status_code == 409
    transactions = client.get("/transactions").json()["transactions"]
    assert len(transactions) == 1
    assert AuditLedgerRepository(ledger).load_entries()[0]["transaction_id"] == "TX-E2E-1"


def test_recording_validation_returns_field_level_422():
    client = TestClient(main.app)
    response = client.post("/record", json={"amount": 0})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_mobile_recording_workflow_uses_temporary_ledger(monkeypatch, tmp_path):
    ledger = tmp_path / "audit_log.json"
    ledger.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(main, "AUDIT_FILE", str(ledger))
    client = TestClient(main.app)
    payload = {"network": "MTN", "phone_number": "0772123456", "amount": 5000, "member_id": "M001", "description": "Simulation"}
    response = client.post("/record_mobile", json=payload)
    assert response.status_code == 200
    assert response.json()["transaction"]["method"] == "Mobile Money Simulation"
