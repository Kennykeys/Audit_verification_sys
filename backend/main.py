from datetime import datetime
import json
import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

from backend.config import Settings
from backend.repository import AuditLedgerRepository, DuplicateTransactionError, LedgerCorruptionError
from backend.schemas import LedgerIntegrityResult
from backend.services.audit_service import AuditService

settings = Settings.from_environment()

app = FastAPI(title="Tamper-Evident Audit System", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIT_FILE = str(settings.ledger_path)


def get_audit_repository():
    return AuditLedgerRepository(AUDIT_FILE)


def get_audit_service():
    return AuditService(get_audit_repository())


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


@app.post("/record")
def record_transaction(entry: dict):
    entry["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    entry["method"] = "Admin"
    entry["hash"] = compute_entry_hash(entry)
    try:
        persisted_entry = get_audit_service().record_entry(entry)
    except DuplicateTransactionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except LedgerCorruptionError as error:
        raise HTTPException(status_code=409, detail="Ledger integrity verification failed") from error
    return {"message": "Transaction recorded successfully", "transaction": persisted_entry}


@app.post("/record_mobile")
def record_mobile_transaction(entry: dict):
    entry["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    entry["method"] = "Mobile Money"
    entry["hash"] = compute_entry_hash(entry)
    try:
        persisted_entry = get_audit_service().record_entry(entry)
    except DuplicateTransactionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
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


@app.get("/transactions")
def get_transactions():
    return {"transactions": load_audit_log()}
