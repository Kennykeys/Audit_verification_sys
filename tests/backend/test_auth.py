from datetime import datetime, timedelta, timezone
import secrets
import bcrypt
import pytest
from fastapi import HTTPException
from backend.auth import AuthenticationService, UNIFORM_LOGIN_FAILURE
from backend.config import Settings

def service_for(tmp_path, password, role="administrator", ttl=60, clock=None):
    return AuthenticationService(Settings(ledger_path=tmp_path/"ledger.json",admin_username="test-operator",admin_password_hash=bcrypt.hashpw(password.encode(),bcrypt.gensalt(rounds=4)).decode(),admin_role=role,session_ttl_seconds=ttl),clock=clock)

def test_login_authenticate_and_logout(tmp_path):
    password=secrets.token_urlsafe(18); service=service_for(tmp_path,password); token,principal,_=service.login("test-operator",password); assert service.authenticate(f"Bearer {token}")==principal; service.logout(f"Bearer {token}")
    with pytest.raises(HTTPException) as error: service.authenticate(f"Bearer {token}")
    assert error.value.status_code==401

def test_login_failure_is_uniform(tmp_path):
    password=secrets.token_urlsafe(18); service=service_for(tmp_path,password)
    for username,candidate in (("missing",password),("test-operator","incorrect")):
        with pytest.raises(HTTPException) as error: service.login(username,candidate)
        assert error.value.status_code==401 and error.value.detail==UNIFORM_LOGIN_FAILURE

def test_expired_session_is_rejected(tmp_path):
    password=secrets.token_urlsafe(18); now=datetime.now(timezone.utc); moments=iter((now,now+timedelta(seconds=61))); service=service_for(tmp_path,password,ttl=60,clock=lambda:next(moments)); token,_,_=service.login("test-operator",password)
    with pytest.raises(HTTPException) as error: service.authenticate(f"Bearer {token}")
    assert error.value.status_code==401

def test_insufficient_role_returns_403(tmp_path):
    password=secrets.token_urlsafe(18); service=service_for(tmp_path,password,role="auditor"); token,_,_=service.login("test-operator",password)
    with pytest.raises(HTTPException) as error: service.require_role(f"Bearer {token}","administrator")
    assert error.value.status_code==403
