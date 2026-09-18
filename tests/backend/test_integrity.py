from copy import deepcopy

import pytest

from backend.integrity import canonicalize_entry, compute_entry_hash, compute_legacy_hash, normalize_amount, verify_entry_hash, verify_legacy_hash


def sample_entry():
    return {
        "transaction_id": " tx-001 ",
        "amount": "50000.00",
        "member_id": " M001 ",
        "description": "Cafe\u0301 payment",
        "timestamp": "2026-09-14T18:30:00+03:00",
        "method": " Manual ",
        "network": None,
        "phone_number": None,
    }


def test_golden_vector():
    assert compute_entry_hash(sample_entry()) == "f04946e17e0fe9dea34156936f5dbe7deb1c169d3436f81dc347e03d7192bb53"


def test_dictionary_order_does_not_change_hash():
    entry = sample_entry()
    assert compute_entry_hash(entry) == compute_entry_hash(dict(reversed(tuple(entry.items()))))


def test_repeated_canonical_output_is_stable():
    entry = sample_entry()
    assert canonicalize_entry(entry) == canonicalize_entry(deepcopy(entry))


@pytest.mark.parametrize("field,value", [("amount", "50001"), ("member_id", "M002"), ("description", "Different"), ("method", "mobile_money"), ("timestamp", "2026-09-14T15:30:01Z")])
def test_included_field_change_changes_hash(field, value):
    entry = sample_entry()
    changed = deepcopy(entry)
    changed[field] = value
    assert compute_entry_hash(entry) != compute_entry_hash(changed)


def test_derived_fields_are_excluded():
    entry = sample_entry()
    changed = deepcopy(entry)
    changed.update({"hash": "ignored", "verified": True, "status": "ignored"})
    assert compute_entry_hash(entry) == compute_entry_hash(changed)


def test_unicode_decimal_and_timestamp_normalization():
    first = sample_entry()
    second = sample_entry()
    second["description"] = "Café payment"
    second["amount"] = 50000
    second["timestamp"] = "2026-09-14T15:30:00Z"
    assert compute_entry_hash(first) == compute_entry_hash(second)


def test_hash_verification_and_legacy_compatibility():
    entry = sample_entry()
    entry["hash"] = compute_entry_hash(entry)
    assert verify_entry_hash(entry)
    legacy = {"transaction_id": "TX-9", "amount": 10, "member_id": "M1", "description": "Legacy", "created_at": "2026-09-01 10:00:00", "method": "Admin"}
    legacy["hash"] = compute_legacy_hash(legacy)
    assert verify_legacy_hash(legacy)


def test_normalize_amount_rejects_invalid_values():
    with pytest.raises(ValueError, match="numeric"):
        normalize_amount("invalid")
