from datetime import datetime
import json
import os

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

app = FastAPI(title="Tamper-Evident Audit System", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIT_FILE = os.path.join("audit_repo", "audit_log.json")
if not os.path.exists(AUDIT_FILE):
    os.makedirs("audit_repo", exist_ok=True)
    with open(AUDIT_FILE, "w") as audit_file:
        json.dump([], audit_file)


def load_audit_log():
    with open(AUDIT_FILE, "r") as audit_file:
        return json.load(audit_file)


def save_audit_log(log):
    with open(AUDIT_FILE, "w") as audit_file:
        json.dump(log, audit_file, indent=2)


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
    log = load_audit_log()
    if any(existing["transaction_id"] == entry["transaction_id"] for existing in log):
        raise HTTPException(status_code=400, detail="Transaction ID already exists")
    entry["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    entry["method"] = "Admin"
    entry["hash"] = compute_entry_hash(entry)
    add_chain_fields(entry, log)
    log.append(entry)
    save_audit_log(log)
    return {"message": "Transaction recorded successfully", "transaction": entry}


@app.post("/record_mobile")
def record_mobile_transaction(entry: dict):
    log = load_audit_log()
    if any(existing["transaction_id"] == entry["transaction_id"] for existing in log):
        raise HTTPException(status_code=400, detail="Transaction ID already exists")
    entry["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    entry["method"] = "Mobile Money"
    entry["hash"] = compute_entry_hash(entry)
    add_chain_fields(entry, log)
    log.append(entry)
    save_audit_log(log)
    return {"message": "Mobile Money transaction recorded successfully", "transaction": entry}


@app.get("/verify/{transaction_id}")
def verify_transaction(transaction_id: str):
    log = load_audit_log()
    entry = next((existing for existing in log if existing["transaction_id"] == transaction_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Transaction not found")
    linked_valid = verify_chain_entry_hash(entry) and verify_chain_links(log)
    canonical_valid = verify_entry_hash(entry)
    legacy_valid = False if canonical_valid else verify_legacy_hash(entry)
    verified = linked_valid if "entry_hash" in entry else canonical_valid or legacy_valid
    return {
        "transaction_id": entry["transaction_id"],
        "amount": entry["amount"],
        "member_id": entry["member_id"],
        "description": entry["description"],
        "created_at": entry.get("created_at"),
        "method": entry.get("method"),
        "verified": verified,
        "hash_format": "hash-linked-v1" if linked_valid else "canonical-v1" if canonical_valid else "legacy" if legacy_valid else "invalid",
        "status": "Verified" if verified else "Tampered",
    }


@app.get("/transactions")
def get_transactions():
    return {"transactions": load_audit_log()}
