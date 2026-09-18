import hashlib
import hmac
import json
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

CANONICAL_HASH_DOMAIN = "audit-verification:transaction:v1"
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
EXCLUDED_DERIVED_FIELDS = ("hash", "verified", "status")


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


def canonicalize_entry(entry):
    timestamp = entry.get("timestamp", entry.get("date_time", entry.get("created_at", "")))
    canonical = {
        "amount": normalize_amount(entry.get("amount")),
        "description": normalize_text(entry.get("description")),
        "member_id": normalize_text(entry.get("member_id")),
        "method": normalize_text(entry.get("method")).lower(),
        "network": normalize_text(entry.get("network")).lower(),
        "phone_number": normalize_text(entry.get("phone_number")),
        "timestamp": normalize_timestamp(timestamp),
        "transaction_id": normalize_text(entry.get("transaction_id")),
    }
    envelope = {"domain": CANONICAL_HASH_DOMAIN, "entry": canonical}
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_entry_hash(entry):
    return hashlib.sha256(canonicalize_entry(entry).encode("utf-8")).hexdigest()


def verify_entry_hash(entry):
    stored_hash = entry.get("hash")
    if not isinstance(stored_hash, str) or len(stored_hash) != 64:
        return False
    return hmac.compare_digest(stored_hash.lower(), compute_entry_hash(entry))


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
