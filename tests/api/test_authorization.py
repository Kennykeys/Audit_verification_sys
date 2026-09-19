import secrets
import bcrypt
from fastapi.testclient import TestClient
from backend import main
from backend.auth import AuthenticationService
from backend.config import Settings

def configured_client(monkeypatch,tmp_path,role="administrator"):
    password=secrets.token_urlsafe(18); service=AuthenticationService(Settings(ledger_path=tmp_path/"ledger.json",admin_username="test-operator",admin_password_hash=bcrypt.hashpw(password.encode(),bcrypt.gensalt(rounds=4)).decode(),admin_role=role,session_ttl_seconds=300)); monkeypatch.setattr(main,"authentication_service",service); client=TestClient(main.app); login=client.post("/auth/login",json={"username":"test-operator","password":password}); assert login.status_code==200; return client,{"Authorization":f"Bearer {login.json()['access_token']}"}

def test_protected_routes_require_authentication():
    client=TestClient(main.app); assert client.get("/transactions").status_code==401; assert client.post("/record",json={}).status_code==401; assert client.post("/record_mobile",json={}).status_code==401

def test_authenticated_principal_logout_and_revocation(monkeypatch,tmp_path):
    client,headers=configured_client(monkeypatch,tmp_path); assert client.get("/auth/me",headers=headers).status_code==200; assert client.post("/auth/logout",headers=headers).status_code==204; assert client.get("/auth/me",headers=headers).status_code==401

def test_insufficient_role_is_forbidden(monkeypatch,tmp_path):
    client,headers=configured_client(monkeypatch,tmp_path,role="auditor"); assert client.get("/transactions",headers=headers).status_code==403

def test_public_integrity_routes_remain_accessible():
    client=TestClient(main.app); assert client.get("/integrity").status_code==200; assert client.get("/integrity/graph").status_code==200; assert client.get("/verify/missing").status_code==404
