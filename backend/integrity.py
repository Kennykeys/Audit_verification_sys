import hashlib
import hmac
import json
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

CANONICAL_HASH_DOMAIN = "audit-verification:transaction:v1"
CHAIN_HASH_DOMAIN = "audit-verification:ledger-entry:v1"
LEDGER_SCHEMA_VERSION = 1
GENESIS_PREVIOUS_HASH = "0" * 64
CHAIN_FIELDS = ("schema_version", "sequence", "previous_hash", "entry_hash")
INCLUDED_FIELDS = (
    "transaction_id",
    "amount",
    "member_id",
    "description",
    "timestamp",
    "method",
    "network",
    "phone_number",
)
EXCLUDED_DERIVED_FIELDS = ("hash", "entry_hash", "verified", "status")


def normalize_text(value):
    if value is None:
        return ""
    return unicodedata.normalize("NFC", str(value).strip())


def normalize_amount(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Transaction amount must be numeric") from error
    if not amount.is_finite():
        raise ValueError("Transaction amount must be finite")
    if amount == 0:
        amount = Decimal(0)
    return format(amount.normalize(), "f")


def normalize_timestamp(value):
    text = normalize_text(value)
    if not text:
        return ""
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_payload(entry):
    timestamp = entry.get("timestamp", entry.get("date_time", entry.get("created_at", "")))
    return {
        "amount": normalize_amount(entry.get("amount")),
        "description": normalize_text(entry.get("description")),
        "member_id": normalize_text(entry.get("member_id")),
        "method": normalize_text(entry.get("method")).lower(),
        "network": normalize_text(entry.get("network")).lower(),
        "phone_number": normalize_text(entry.get("phone_number")),
        "timestamp": normalize_timestamp(timestamp),
        "transaction_id": normalize_text(entry.get("transaction_id")),
    }


def canonicalize_entry(entry):
    envelope = {"domain": CANONICAL_HASH_DOMAIN, "entry": canonical_payload(entry)}
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_entry_hash(entry):
    return hashlib.sha256(canonicalize_entry(entry).encode("utf-8")).hexdigest()


def verify_entry_hash(entry):
    stored_hash = entry.get("hash")
    if not isinstance(stored_hash, str) or len(stored_hash) != 64:
        return False
    return hmac.compare_digest(stored_hash.lower(), compute_entry_hash(entry))


def canonicalize_chain_entry(entry):
    envelope = {
        "domain": CHAIN_HASH_DOMAIN,
        "entry": canonical_payload(entry),
        "previous_hash": normalize_text(entry.get("previous_hash")).lower(),
        "schema_version": entry.get("schema_version"),
        "sequence": entry.get("sequence"),
    }
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_chain_entry_hash(entry):
    return hashlib.sha256(canonicalize_chain_entry(entry).encode("utf-8")).hexdigest()


def verify_chain_entry_hash(entry):
    stored_hash = entry.get("entry_hash")
    if not isinstance(stored_hash, str) or len(stored_hash) != 64:
        return False
    return hmac.compare_digest(stored_hash.lower(), compute_chain_entry_hash(entry))


def classify_ledger(entries):
    if not isinstance(entries, list):
        raise ValueError("Ledger root must be a JSON array")
    if any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("Every ledger entry must be a JSON object")
    if not entries:
        return "empty"
    linked_count = sum(all(field in entry for field in CHAIN_FIELDS) for entry in entries)
    legacy_count = sum(not any(field in entry for field in CHAIN_FIELDS) for entry in entries)
    if linked_count == len(entries):
        return "linked"
    if legacy_count == len(entries):
        return "legacy"
    return "mixed"


def migrate_legacy_ledger(entries):
    ledger_format = classify_ledger(entries)
    if ledger_format == "mixed":
        raise ValueError("Mixed legacy and hash-linked ledger formats are not supported")
    if ledger_format == "linked":
        if not verify_chain_links(entries):
            raise ValueError("Existing hash-linked ledger failed verification")
        return deepcopy(entries)
    previous_hash = GENESIS_PREVIOUS_HASH
    migrated = []
    for sequence, source_entry in enumerate(entries, start=1):
        migrated_entry = deepcopy(source_entry)
        migrated_entry["schema_version"] = LEDGER_SCHEMA_VERSION
        migrated_entry["sequence"] = sequence
        migrated_entry["previous_hash"] = previous_hash
        migrated_entry["entry_hash"] = compute_chain_entry_hash(migrated_entry)
        previous_hash = migrated_entry["entry_hash"]
        migrated.append(migrated_entry)
    if not verify_chain_links(migrated):
        raise ValueError("Migrated hash-linked ledger failed verification")
    return migrated


def verify_chain_links(entries):
    try:
        if classify_ledger(entries) not in {"empty", "linked"}:
            return False
    except ValueError:
        return False
    previous_hash = GENESIS_PREVIOUS_HASH
    for expected_sequence, entry in enumerate(entries, start=1):
        if entry.get("schema_version") != LEDGER_SCHEMA_VERSION:
            return False
        if entry.get("sequence") != expected_sequence:
            return False
        if entry.get("previous_hash") != previous_hash:
            return False
        if not verify_chain_entry_hash(entry):
            return False
        previous_hash = entry["entry_hash"]
    return True


def compute_transaction_hash(transaction):
    return compute_entry_hash(transaction)


def verify_transaction_hash(transaction):
    return verify_entry_hash(transaction)


def compute_legacy_hash(entry):
    created_at = entry.get("created_at", "")
    method = entry.get("method", "")
    payload = f"{entry['transaction_id']}|{entry['amount']}|{entry['member_id']}|{entry['description']}|{created_at}|{method}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_legacy_hash(entry):
    stored_hash = entry.get("hash")
    if not isinstance(stored_hash, str) or len(stored_hash) != 64:
        return False
    return hmac.compare_digest(stored_hash.lower(), compute_legacy_hash(entry))
