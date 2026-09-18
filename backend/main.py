from datetime import datetime
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.integrity import compute_entry_hash, verify_entry_hash, verify_legacy_hash

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


@app.post("/record")
def record_transaction(entry: dict):
    log = load_audit_log()
    if any(existing["transaction_id"] == entry["transaction_id"] for existing in log):
        raise HTTPException(status_code=400, detail="Transaction ID already exists")
    entry["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    entry["method"] = "Admin"
    entry["hash"] = compute_entry_hash(entry)
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
    log.append(entry)
    save_audit_log(log)
    return {"message": "Mobile Money transaction recorded successfully", "transaction": entry}


@app.get("/verify/{transaction_id}")
def verify_transaction(transaction_id: str):
    log = load_audit_log()
    entry = next((existing for existing in log if existing["transaction_id"] == transaction_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Transaction not found")
    canonical_valid = verify_entry_hash(entry)
    legacy_valid = False if canonical_valid else verify_legacy_hash(entry)
    return {
        "transaction_id": entry["transaction_id"],
        "amount": entry["amount"],
        "member_id": entry["member_id"],
        "description": entry["description"],
        "created_at": entry.get("created_at"),
        "method": entry.get("method"),
        "verified": canonical_valid or legacy_valid,
        "hash_format": "canonical-v1" if canonical_valid else "legacy" if legacy_valid else "invalid",
        "status": "Verified" if canonical_valid or legacy_valid else "Tampered",
    }


@app.get("/transactions")
def get_transactions():
    return {"transactions": load_audit_log()}
