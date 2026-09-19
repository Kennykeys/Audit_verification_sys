import argparse
import json
import os
import shutil
from pathlib import Path

from backend.integrity import classify_ledger, migrate_legacy_ledger, verify_chain_links


class MigrationError(RuntimeError):
    pass


def load_ledger(ledger_path):
    try:
        with ledger_path.open("r", encoding="utf-8") as ledger_file:
            entries = json.load(ledger_file)
    except (OSError, json.JSONDecodeError) as error:
        raise MigrationError(f"Unable to read valid ledger JSON: {error}") from error
    try:
        classify_ledger(entries)
    except ValueError as error:
        raise MigrationError(str(error)) from error
    return entries


def migrate_ledger_file(ledger_path, backup_path):
    ledger_path = Path(ledger_path)
    backup_path = Path(backup_path)
    entries = load_ledger(ledger_path)
    ledger_format = classify_ledger(entries)
    if ledger_format == "mixed":
        raise MigrationError("Mixed legacy and hash-linked ledger formats are not supported")
    if ledger_format == "linked":
        if not verify_chain_links(entries):
            raise MigrationError("Existing hash-linked ledger failed verification")
        return entries, False
    if backup_path.exists():
        raise MigrationError(f"Backup already exists: {backup_path}")
    try:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        with backup_path.open("xb") as backup_file:
            with ledger_path.open("rb") as source_file:
                shutil.copyfileobj(source_file, backup_file)
            backup_file.flush()
            os.fsync(backup_file.fileno())
    except OSError as error:
        raise MigrationError(f"Unable to create pre-chain backup: {error}") from error
    migrated = migrate_legacy_ledger(entries)
    if not verify_chain_links(migrated):
        raise MigrationError("Migrated ledger failed chain verification")
    temporary_path = ledger_path.with_name(f".{ledger_path.name}.phase4.tmp")
    try:
        with temporary_path.open("x", encoding="utf-8", newline="\n") as temporary_file:
            json.dump(migrated, temporary_file, indent=2, ensure_ascii=False)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, ledger_path)
    except OSError as error:
        temporary_path.unlink(missing_ok=True)
        raise MigrationError(f"Unable to replace ledger after verified migration: {error}") from error
    persisted = load_ledger(ledger_path)
    if not verify_chain_links(persisted):
        raise MigrationError("Persisted migrated ledger failed verification")
    return persisted, True


def main():
    parser = argparse.ArgumentParser(description="Migrate a legacy audit ledger to hash-linked format")
    parser.add_argument("--ledger", default="backend/audit_repo/audit_log.json")
    parser.add_argument("--backup", default="backend/audit_repo/audit_log.pre-chain.json")
    arguments = parser.parse_args()
    migrated, changed = migrate_ledger_file(arguments.ledger, arguments.backup)
    print(f"Ledger entries verified: {len(migrated)}")
    print(f"Migration applied: {'yes' if changed else 'no'}")


if __name__ == "__main__":
    main()
