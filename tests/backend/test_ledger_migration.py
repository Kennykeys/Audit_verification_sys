import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.integrity import GENESIS_PREVIOUS_HASH, migrate_legacy_ledger, verify_chain_links
from backend.migrate_ledger import MigrationError, migrate_ledger_file

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "legacy_audit_log.json"
CHAIN_FIELDS = {"schema_version", "sequence", "previous_hash", "entry_hash"}


def load_fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def business_data(entry):
    return {key: value for key, value in entry.items() if key not in CHAIN_FIELDS}


def test_migration_preserves_business_data_and_original_order():
    legacy = load_fixture()
    migrated = migrate_legacy_ledger(legacy)
    assert [business_data(entry) for entry in migrated] == legacy
    assert [entry["sequence"] for entry in migrated] == list(range(1, len(legacy) + 1))
    assert migrated[0]["previous_hash"] == GENESIS_PREVIOUS_HASH
    assert verify_chain_links(migrated)


def test_every_previous_hash_references_preceding_entry_hash():
    migrated = migrate_legacy_ledger(load_fixture())
    for previous, current in zip(migrated, migrated[1:]):
        assert current["previous_hash"] == previous["entry_hash"]


def test_migration_is_idempotent_for_verified_linked_ledgers():
    migrated = migrate_legacy_ledger(load_fixture())
    assert migrate_legacy_ledger(migrated) == migrated


def test_migration_refuses_mixed_format_ledgers():
    mixed = load_fixture()
    mixed[0]["schema_version"] = 1
    with pytest.raises(ValueError, match="Mixed legacy and hash-linked"):
        migrate_legacy_ledger(mixed)


@pytest.mark.parametrize("mutation", ["modified", "deleted", "reordered", "inserted"])
def test_chain_verification_detects_structural_and_payload_tampering(mutation):
    migrated = migrate_legacy_ledger(load_fixture())
    tampered = deepcopy(migrated)
    if mutation == "modified":
        tampered[1]["amount"] = tampered[1]["amount"] + 1
    elif mutation == "deleted":
        del tampered[1]
    elif mutation == "reordered":
        tampered[0], tampered[1] = tampered[1], tampered[0]
    else:
        tampered.insert(1, deepcopy(tampered[0]))
    assert not verify_chain_links(tampered)


def test_file_migration_creates_exact_backup_before_replacement(tmp_path):
    source = tmp_path / "audit_log.json"
    backup = tmp_path / "audit_log.pre-chain.json"
    original_bytes = FIXTURE_PATH.read_bytes()
    source.write_bytes(original_bytes)
    migrated, changed = migrate_ledger_file(source, backup)
    assert changed is True
    assert backup.read_bytes() == original_bytes
    assert json.loads(source.read_text(encoding="utf-8")) == migrated
    assert verify_chain_links(migrated)


def test_file_migration_refuses_existing_backup_without_replacing_source(tmp_path):
    source = tmp_path / "audit_log.json"
    backup = tmp_path / "audit_log.pre-chain.json"
    original_bytes = FIXTURE_PATH.read_bytes()
    source.write_bytes(original_bytes)
    backup.write_text("existing", encoding="utf-8")
    with pytest.raises(MigrationError, match="Backup already exists"):
        migrate_ledger_file(source, backup)
    assert source.read_bytes() == original_bytes


def test_existing_verified_linked_file_is_not_rewritten(tmp_path):
    source = tmp_path / "audit_log.json"
    backup = tmp_path / "audit_log.pre-chain.json"
    migrated = migrate_legacy_ledger(load_fixture())
    source.write_text(json.dumps(migrated, indent=2) + "\n", encoding="utf-8")
    original_bytes = source.read_bytes()
    returned, changed = migrate_ledger_file(source, backup)
    assert changed is False
    assert returned == migrated
    assert source.read_bytes() == original_bytes
    assert not backup.exists()
