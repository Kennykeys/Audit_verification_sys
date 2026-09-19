import json
from pathlib import Path

import pytest

from backend.integrity import GENESIS_PREVIOUS_HASH, verify_chain_links
from backend.repository import AuditLedgerRepository, LedgerCorruptionError, UnsafeLedgerPathError


def make_repository(tmp_path):
    ledger_path = tmp_path / "audit_log.json"
    ledger_path.write_text("[]\n", encoding="utf-8")
    return AuditLedgerRepository(ledger_path), ledger_path


def sample_entry(identifier):
    return {"transaction_id": identifier, "amount": 100, "member_id": "M001", "description": "Test", "created_at": "2026-09-19T12:00:00Z", "method": "Admin", "network": None, "phone_number": None}


def test_default_repository_path_is_independent_of_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from backend.config import Settings, DEFAULT_LEDGER_PATH
    assert Settings.from_environment().ledger_path == DEFAULT_LEDGER_PATH


def test_append_entry_builds_and_verifies_chain(tmp_path):
    repository, ledger_path = make_repository(tmp_path)
    first = repository.append_entry(sample_entry("TX-1"))
    second = repository.append_entry(sample_entry("TX-2"))
    entries = repository.load_entries()
    assert first["sequence"] == 1
    assert first["previous_hash"] == GENESIS_PREVIOUS_HASH
    assert second["sequence"] == 2
    assert second["previous_hash"] == first["entry_hash"]
    assert verify_chain_links(entries)
    assert json.loads(ledger_path.read_text(encoding="utf-8")) == entries


def test_malformed_json_raises_without_reinitializing(tmp_path):
    ledger_path = tmp_path / "audit_log.json"
    ledger_path.write_text("not-json", encoding="utf-8")
    repository = AuditLedgerRepository(ledger_path)
    with pytest.raises(LedgerCorruptionError):
        repository.load_entries()
    assert ledger_path.read_text(encoding="utf-8") == "not-json"


def test_atomic_write_failure_removes_temporary_file(monkeypatch, tmp_path):
    repository, ledger_path = make_repository(tmp_path)
    monkeypatch.setattr("backend.repository.os.replace", lambda source, destination: (_ for _ in ()).throw(OSError("simulated failure")))
    with pytest.raises(OSError):
        repository.append_entry(sample_entry("TX-FAIL"))
    assert json.loads(ledger_path.read_text(encoding="utf-8")) == []
    assert list(tmp_path.glob(".audit-ledger-*.tmp")) == []


def test_symlink_ledger_is_rejected(tmp_path):
    target = tmp_path / "target.json"
    target.write_text("[]\n", encoding="utf-8")
    link = tmp_path / "audit_log.json"
    link.symlink_to(target)
    with pytest.raises(UnsafeLedgerPathError):
        AuditLedgerRepository(link).load_entries()
