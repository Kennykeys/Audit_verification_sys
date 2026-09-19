from copy import deepcopy

import pytest

from backend.integrity import migrate_legacy_ledger
from backend.services.audit_service import AuditService


class StubRepository:
    def __init__(self, entries):
        self.entries = entries

    def load_entries(self):
        return deepcopy(self.entries)

    def append_entry(self, entry):
        return entry


def legacy(identifier, amount=10):
    return {"transaction_id": identifier, "amount": amount, "member_id": "M001", "description": "Test", "created_at": "2026-09-19T12:00:00Z", "method": "Admin", "network": None, "phone_number": None}


def linked_entries():
    return migrate_legacy_ledger([legacy("TX-1"), legacy("TX-2", 20), legacy("TX-3", 30)])


def test_valid_ledger_reports_complete_evidence():
    entries = linked_entries()
    result = AuditService(StubRepository(entries)).verify_ledger()
    assert result.valid is True
    assert result.entries_checked == 3
    assert result.total_entries == 3
    assert result.ledger_head_hash == entries[-1]["entry_hash"]
    assert result.first_invalid_entry is None


def test_empty_ledger_is_valid():
    result = AuditService(StubRepository([])).verify_ledger()
    assert result.valid is True
    assert result.entries_checked == 0
    assert result.ledger_head_hash is None


@pytest.mark.parametrize("mutation,failure_type", [("altered", "entry_hash"), ("deleted", "sequence"), ("reordered", "sequence"), ("schema", "schema_version")])
def test_first_invalid_entry_is_reported(mutation, failure_type):
    entries = linked_entries()
    if mutation == "altered":
        entries[1]["amount"] = 99
    elif mutation == "deleted":
        del entries[1]
    elif mutation == "reordered":
        entries[0], entries[1] = entries[1], entries[0]
    else:
        entries[1]["schema_version"] = 2
    result = AuditService(StubRepository(entries)).verify_ledger()
    assert result.valid is False
    assert result.first_invalid_entry.failure_type == failure_type
    assert result.entries_checked < result.total_entries


def test_individual_verification_includes_ledger_context():
    entries = linked_entries()
    entries[2]["amount"] = 999
    result = AuditService(StubRepository(entries)).verify_transaction("TX-1")
    assert result["record_valid"] is True
    assert result["ledger_context_valid"] is False
    assert result["verified"] is False
