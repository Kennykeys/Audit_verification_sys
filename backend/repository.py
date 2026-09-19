import copy
import fcntl
import json
import os
import tempfile
from pathlib import Path

try:
    from backend.integrity import GENESIS_PREVIOUS_HASH, LEDGER_SCHEMA_VERSION, compute_chain_entry_hash, verify_chain_links
except ModuleNotFoundError:
    from integrity import GENESIS_PREVIOUS_HASH, LEDGER_SCHEMA_VERSION, compute_chain_entry_hash, verify_chain_links


class AuditLedgerRepositoryError(RuntimeError):
    pass


class LedgerCorruptionError(AuditLedgerRepositoryError):
    pass


class UnsafeLedgerPathError(AuditLedgerRepositoryError):
    pass


class DuplicateTransactionError(AuditLedgerRepositoryError):
    pass


class AuditLedgerRepository:
    def __init__(self, ledger_path):
        self.ledger_path = Path(os.path.abspath(os.fspath(Path(ledger_path).expanduser())))
        self.lock_path = self.ledger_path.with_name(".audit-ledger.lock")

    def _validate_path(self):
        if self.ledger_path.is_symlink():
            raise UnsafeLedgerPathError("Ledger path must not be a symbolic link")
        if not self.ledger_path.parent.exists():
            raise FileNotFoundError("Ledger directory does not exist")
        if self.ledger_path.exists() and not self.ledger_path.is_file():
            raise UnsafeLedgerPathError("Ledger path must reference a regular file")

    def _lock(self, exclusive):
        self._validate_path()
        descriptor = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(descriptor, operation)
        return descriptor

    def _unlock(self, descriptor):
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    def _load_unlocked(self):
        self._validate_path()
        if not self.ledger_path.exists():
            raise FileNotFoundError("Ledger file does not exist")
        try:
            with self.ledger_path.open("r", encoding="utf-8") as ledger_stream:
                entries = json.load(ledger_stream)
        except (OSError, json.JSONDecodeError) as error:
            raise LedgerCorruptionError("Ledger cannot be read as valid JSON") from error
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            raise LedgerCorruptionError("Ledger must contain a list of objects")
        if entries and not verify_chain_links(entries):
            raise LedgerCorruptionError("Ledger chain integrity validation failed")
        return entries

    def load_entries(self):
        descriptor = self._lock(exclusive=False)
        try:
            return copy.deepcopy(self._load_unlocked())
        finally:
            self._unlock(descriptor)

    def _atomic_write_unlocked(self, entries):
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            raise LedgerCorruptionError("Ledger must contain a list of objects")
        if entries and not verify_chain_links(entries):
            raise LedgerCorruptionError("Refusing to persist an invalid ledger chain")
        temporary_name = None
        descriptor = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(prefix=".audit-ledger-", suffix=".tmp", dir=self.ledger_path.parent)
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_stream:
                descriptor = None
                json.dump(entries, temporary_stream, ensure_ascii=False, indent=2)
                temporary_stream.write("\n")
                temporary_stream.flush()
                os.fsync(temporary_stream.fileno())
            os.replace(temporary_name, self.ledger_path)
            temporary_name = None
            directory_descriptor = os.open(self.ledger_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
            if self._load_unlocked() != entries:
                raise AuditLedgerRepositoryError("Persisted ledger verification failed")
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if temporary_name is not None and os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def atomic_write(self, entries):
        descriptor = self._lock(exclusive=True)
        try:
            self._atomic_write_unlocked(copy.deepcopy(entries))
        finally:
            self._unlock(descriptor)

    def append_entry(self, entry):
        descriptor = self._lock(exclusive=True)
        try:
            entries = self._load_unlocked()
            transaction_id = entry.get("transaction_id")
            if any(existing.get("transaction_id") == transaction_id for existing in entries):
                raise DuplicateTransactionError("Transaction ID already exists")
            persisted_entry = copy.deepcopy(entry)
            persisted_entry["schema_version"] = LEDGER_SCHEMA_VERSION
            persisted_entry["sequence"] = len(entries) + 1
            persisted_entry["previous_hash"] = entries[-1]["entry_hash"] if entries else GENESIS_PREVIOUS_HASH
            persisted_entry["entry_hash"] = compute_chain_entry_hash(persisted_entry)
            entries.append(persisted_entry)
            self._atomic_write_unlocked(entries)
            return copy.deepcopy(persisted_entry)
        finally:
            self._unlock(descriptor)
