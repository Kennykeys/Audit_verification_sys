from pathlib import Path

from fastapi.testclient import TestClient
import bcrypt
import secrets

from backend.auth import AuthenticationService
from backend.config import Settings

from backend import main

def authenticated_client(monkeypatch,tmp_path):
    password=secrets.token_urlsafe(18)
    service=AuthenticationService(Settings(ledger_path=tmp_path/"auth-ledger.json",admin_username="test-operator",admin_password_hash=bcrypt.hashpw(password.encode(),bcrypt.gensalt(rounds=4)).decode(),admin_role="administrator",session_ttl_seconds=300))
    monkeypatch.setattr(main,"authentication_service",service)
    client=TestClient(main.app)
    login=client.post("/auth/login",json={"username":"test-operator","password":password})
    assert login.status_code==200
    return client,{"Authorization":f"Bearer {login.json()['access_token']}"}
from backend.repository import AuditLedgerRepository


def test_recording_workflow_uses_temporary_ledger(monkeypatch, tmp_path):
    ledger = tmp_path / "audit_log.json"
    ledger.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(main, "AUDIT_FILE", str(ledger))
    client, headers = authenticated_client(monkeypatch, tmp_path)
    payload = {"transaction_id": "TX-E2E-1", "amount": 2500, "member_id": "M001", "description": "Contract test"}
    response = client.post("/record", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["transaction"]["sequence"] == 1
    assert client.post("/record", json=payload, headers=headers).status_code == 409
    transactions = client.get("/transactions", headers=headers).json()["transactions"]
    assert len(transactions) == 1
    assert AuditLedgerRepository(ledger).load_entries()[0]["transaction_id"] == "TX-E2E-1"


def test_recording_validation_returns_field_level_422(monkeypatch, tmp_path):
    client, headers = authenticated_client(monkeypatch, tmp_path)
    response = client.post("/record", json={"amount": 0}, headers=headers)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_mobile_recording_workflow_uses_temporary_ledger(monkeypatch, tmp_path):
    ledger = tmp_path / "audit_log.json"
    ledger.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(main, "AUDIT_FILE", str(ledger))
    client, headers = authenticated_client(monkeypatch, tmp_path)
    payload = {"network": "MTN", "phone_number": "0772123456", "amount": 5000, "member_id": "M001", "description": "Simulation"}
    response = client.post("/record_mobile", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["transaction"]["method"] == "Mobile Money Simulation"
