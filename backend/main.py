from datetime import datetime
import json
import os
from pathlib import Path
import sys
import uuid

if __package__ in {None, ""}:
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.integrity import (
    GENESIS_PREVIOUS_HASH,
    LEDGER_SCHEMA_VERSION,
    classify_ledger,
    compute_chain_entry_hash,
    compute_entry_hash,
    verify_chain_entry_hash,
    verify_chain_links,
    verify_entry_hash,
    verify_legacy_hash,
)

from backend.auth import AuthenticationService
from backend.config import Settings
from backend.repository import AuditLedgerRepository, DuplicateTransactionError, LedgerCorruptionError
from backend.schemas import AuthenticationLoginRequest, AuthenticationTokenResponse, AuthenticatedPrincipal, IntegrityGraphResult, LedgerIntegrityResult
from pydantic import BaseModel, Field
from backend.services.audit_service import AuditService
from backend.security import SecurityBoundaryMiddleware

settings = Settings.from_environment()
authentication_service = AuthenticationService(settings)

app = FastAPI(title="Tamper-Evident Audit System", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))
app.add_middleware(SecurityBoundaryMiddleware, settings=settings)
if settings.https_redirect:
    app.add_middleware(HTTPSRedirectMiddleware)

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    details = exc.errors()
    return JSONResponse(
        status_code=422,
        content={
            "detail": details,
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": details,
                "request_id": getattr(request.state, "request_id", None),
            },
        },
    )

@app.exception_handler(Exception)
async def unhandled_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "An internal server error occurred", "request_id": request.headers.get("x-request-id")}})

class RecordTransactionRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=128)
    amount: float = Field(gt=0)
    member_id: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=500)


class RecordMobileRequest(BaseModel):
    network: str = Field(min_length=1, max_length=64)
    phone_number: str = Field(min_length=7, max_length=32)
    amount: float = Field(gt=0)
    member_id: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=500)


AUDIT_FILE = str(settings.ledger_path)


def get_audit_repository():
    return AuditLedgerRepository(AUDIT_FILE)


def get_audit_service():
    return AuditService(get_audit_repository())

def get_authentication_service():
    return authentication_service

def require_authenticated_principal(authorization: str | None = Header(default=None)):
    return get_authentication_service().authenticate(authorization)

def require_administrator(authorization: str | None = Header(default=None)):
    return get_authentication_service().require_role(authorization, "administrator")


def load_audit_log():
    try:
        return get_audit_repository().load_entries()
    except LedgerCorruptionError as error:
        raise HTTPException(status_code=500, detail="Audit ledger integrity validation failed") from error


def compute_hash(entry):
    return compute_entry_hash(entry)


def add_chain_fields(entry, log):
    ledger_format = classify_ledger(log)
    if ledger_format not in {"empty", "linked"}:
        raise HTTPException(status_code=409, detail="Ledger migration is required before recording new transactions")
    if ledger_format == "linked" and not verify_chain_links(log):
        raise HTTPException(status_code=409, detail="Ledger integrity verification failed")
    entry["schema_version"] = LEDGER_SCHEMA_VERSION
    entry["sequence"] = len(log) + 1
    entry["previous_hash"] = log[-1]["entry_hash"] if log else GENESIS_PREVIOUS_HASH
    entry["entry_hash"] = compute_chain_entry_hash(entry)
    return entry


@app.post("/auth/login", response_model=AuthenticationTokenResponse)
def login(request: AuthenticationLoginRequest):
    token, principal, expires_at = get_authentication_service().login(request.username, request.password)
    return AuthenticationTokenResponse(access_token=token, expires_at=expires_at, principal=principal)

@app.get("/auth/me", response_model=AuthenticatedPrincipal)
def authenticated_principal(principal: AuthenticatedPrincipal = Depends(require_authenticated_principal)):
    return principal

@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(authorization: str | None = Header(default=None)):
    get_authentication_service().logout(authorization)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.post("/record")
def record_transaction(request: RecordTransactionRequest, _principal: AuthenticatedPrincipal = Depends(require_administrator)):
    entry = request.model_dump()
    entry["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    entry["method"] = "Admin"
    entry["hash"] = compute_entry_hash(entry)
    try:
        persisted_entry = get_audit_service().record_entry(entry)
    except DuplicateTransactionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except LedgerCorruptionError as error:
        raise HTTPException(status_code=409, detail="Ledger integrity verification failed") from error
    return {"message": "Transaction recorded successfully", "transaction": persisted_entry}


@app.post("/record_mobile")
def record_mobile_transaction(request: RecordMobileRequest, _principal: AuthenticatedPrincipal = Depends(require_administrator)):
    entry = request.model_dump()
    entry["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    entry["transaction_id"] = "MM-" + uuid.uuid4().hex
    entry["method"] = "Mobile Money Simulation"
    entry["hash"] = compute_entry_hash(entry)
    try:
        persisted_entry = get_audit_service().record_entry(entry)
    except DuplicateTransactionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except LedgerCorruptionError as error:
        raise HTTPException(status_code=409, detail="Ledger integrity verification failed") from error
    return {"message": "Mobile Money transaction recorded successfully", "transaction": persisted_entry}


@app.get("/verify/{transaction_id}")
def verify_transaction(transaction_id: str):
    result = get_audit_service().verify_transaction(transaction_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@app.get("/integrity", response_model=LedgerIntegrityResult)
def verify_ledger_integrity():
    return get_audit_service().verify_ledger()


@app.get("/integrity/graph", response_model=IntegrityGraphResult)
def get_integrity_graph():
    return get_audit_service().build_integrity_graph()


@app.get("/transactions")
def get_transactions(_principal: AuthenticatedPrincipal = Depends(require_administrator)):
    return {"transactions": load_audit_log()}
