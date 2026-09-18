import json

import pytest
from fastapi.testclient import TestClient

from backend import auth_backend
from backend.integrity import verify_transaction_hash


@pytest.fixture
def isolated_client(tmp_path, monkeypatch):
    ledger_file = tmp_path / "audit_log.json"
    ledger_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(auth_backend, "AUDIT_LOG", str(ledger_file))
    return TestClient(auth_backend.app), ledger_file


def test_manual_transaction_receives_deterministic_hash(isolated_client):
    client, ledger_file = isolated_client
    payload = {"transaction_id": "TX-100", "amount": 50000, "member_id": "M001", "description": "Loan repayment", "method": "manual"}
    response = client.post("/transactions", json=payload)
    assert response.status_code == 200
    transaction = response.json()["transaction"]
    assert len(transaction["hash"]) == 64
    assert verify_transaction_hash(transaction)
    assert json.loads(ledger_file.read_text(encoding="utf-8")) == [transaction]


def test_duplicate_transaction_identifier_is_rejected(isolated_client):
    client, ledger_file = isolated_client
    payload = {"transaction_id": "TX-101", "amount": 1000, "member_id": "M001", "description": "Deposit", "method": "manual"}
    assert client.post("/transactions", json=payload).status_code == 200
    response = client.post("/transactions", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == "Transaction ID already exists"
    assert len(json.loads(ledger_file.read_text(encoding="utf-8"))) == 1


def test_verification_reports_verified_and_tampered(isolated_client):
    client, ledger_file = isolated_client
    payload = {"transaction_id": "TX-102", "amount": 2500, "member_id": "M002", "description": "Savings", "method": "manual"}
    assert client.post("/transactions", json=payload).status_code == 200
    verified = client.get("/verify/TX-102")
    assert verified.status_code == 200
    assert verified.json() == {"transaction_id": "TX-102", "verified": True, "status": "verified"}
    records = json.loads(ledger_file.read_text(encoding="utf-8"))
    records[0]["amount"] = 2501
    ledger_file.write_text(json.dumps(records), encoding="utf-8")
    tampered = client.get("/verify/TX-102")
    assert tampered.status_code == 200
    assert tampered.json() == {"transaction_id": "TX-102", "verified": False, "status": "tampered"}


def test_missing_transaction_returns_not_found(isolated_client):
    client, _ledger_file = isolated_client
    response = client.get("/verify/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "Transaction not found"


def test_mobile_money_transaction_receives_deterministic_hash(isolated_client, monkeypatch):
    client, ledger_file = isolated_client
    monkeypatch.setattr(auth_backend.random, "choice", lambda _choices: True)
    response = client.post("/mobile_money", json={"member_id": "M003", "amount": 4000, "phone_number": "0772123456", "description": "Subscription", "network": "MTN MoMo"})
    assert response.status_code == 200
    transaction = response.json()["transaction"]
    assert len(transaction["hash"]) == 64
    assert verify_transaction_hash(transaction)
    assert json.loads(ledger_file.read_text(encoding="utf-8")) == [transaction]
