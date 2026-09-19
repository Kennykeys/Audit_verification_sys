import hmac

from backend.integrity import GENESIS_PREVIOUS_HASH, LEDGER_SCHEMA_VERSION, compute_chain_entry_hash
from backend.repository import DuplicateTransactionError, LedgerCorruptionError
from backend.schemas import EntryIntegrityResult, IntegrityGraphEdge, IntegrityGraphNode, IntegrityGraphResult, LedgerIntegrityResult


class AuditService:
    def __init__(self, repository):
        self.repository = repository

    def record_entry(self, entry):
        return self.repository.append_entry(entry)

    def verify_entries(self, entries):
        if not isinstance(entries, list):
            return LedgerIntegrityResult(valid=False, total_entries=0, entries_checked=0, first_invalid_entry=EntryIntegrityResult(valid=False, failure_type="malformed_ledger"), ledger_head_hash=None)
        previous_hash = GENESIS_PREVIOUS_HASH
        for expected_sequence, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                return self._failure(entries, expected_sequence - 1, expected_sequence, None, "malformed_entry", "object", type(entry).__name__)
            transaction_id = entry.get("transaction_id")
            if entry.get("schema_version") != LEDGER_SCHEMA_VERSION:
                return self._failure(entries, expected_sequence - 1, expected_sequence, transaction_id, "schema_version", LEDGER_SCHEMA_VERSION, entry.get("schema_version"))
            if entry.get("sequence") != expected_sequence:
                return self._failure(entries, expected_sequence - 1, expected_sequence, transaction_id, "sequence", expected_sequence, entry.get("sequence"))
            if entry.get("previous_hash") != previous_hash:
                return self._failure(entries, expected_sequence - 1, expected_sequence, transaction_id, "previous_hash", previous_hash, entry.get("previous_hash"))
            expected_hash = compute_chain_entry_hash(entry)
            recorded_hash = entry.get("entry_hash")
            if not isinstance(recorded_hash, str) or not hmac.compare_digest(recorded_hash.lower(), expected_hash):
                return self._failure(entries, expected_sequence - 1, expected_sequence, transaction_id, "entry_hash", expected_hash, recorded_hash)
            previous_hash = recorded_hash
        return LedgerIntegrityResult(valid=True, total_entries=len(entries), entries_checked=len(entries), first_invalid_entry=None, ledger_head_hash=entries[-1]["entry_hash"] if entries else None)

    def _failure(self, entries, checked, sequence, transaction_id, failure_type, expected, recorded):
        return LedgerIntegrityResult(valid=False, total_entries=len(entries), entries_checked=checked, first_invalid_entry=EntryIntegrityResult(sequence=sequence, transaction_id=transaction_id, valid=False, failure_type=failure_type, expected_value=str(expected) if expected is not None else None, recorded_value=str(recorded) if recorded is not None else None), ledger_head_hash=None)

    def verify_ledger(self):
        try:
            entries = self.repository.load_entries()
        except (LedgerCorruptionError, ValueError, TypeError):
            return LedgerIntegrityResult(valid=False, total_entries=0, entries_checked=0, first_invalid_entry=EntryIntegrityResult(valid=False, failure_type="malformed_ledger"), ledger_head_hash=None)
        return self.verify_entries(entries)

    def verify_transaction(self, transaction_id):
        try:
            entries = self.repository.load_entries()
        except (LedgerCorruptionError, ValueError, TypeError):
            return {"transaction_id": transaction_id, "verified": False, "record_valid": False, "ledger_context_valid": False, "status": "Tampered", "failure_type": "malformed_ledger"}
        integrity = self.verify_entries(entries)
        entry = next((item for item in entries if item.get("transaction_id") == transaction_id), None)
        if entry is None:
            return None
        expected_hash = compute_chain_entry_hash(entry)
        recorded_hash = entry.get("entry_hash")
        record_valid = isinstance(recorded_hash, str) and hmac.compare_digest(recorded_hash.lower(), expected_hash)
        verified = record_valid and integrity.valid
        return {"transaction_id": transaction_id, "amount": entry.get("amount"), "member_id": entry.get("member_id"), "description": entry.get("description"), "created_at": entry.get("created_at"), "method": entry.get("method"), "verified": verified, "record_valid": record_valid, "ledger_context_valid": integrity.valid, "hash_format": "hash-linked-v1" if record_valid else "invalid", "status": "Verified" if verified else "Tampered", "failure_type": None if verified else integrity.first_invalid_entry.failure_type if integrity.first_invalid_entry else "entry_hash"}

    def build_integrity_graph(self):
        try:
            entries = self.repository.load_entries()
        except (LedgerCorruptionError, ValueError, TypeError):
            return IntegrityGraphResult(
                valid=False,
                total_entries=0,
                entries_checked=0,
                ledger_head_hash=None,
                first_invalid_sequence=None,
                failure_type="malformed_ledger",
                nodes=[],
                edges=[],
            )

        integrity = self.verify_entries(entries)
        invalid_sequence = (
            integrity.first_invalid_entry.sequence
            if integrity.first_invalid_entry is not None
            else None
        )
        failure_type = (
            integrity.first_invalid_entry.failure_type
            if integrity.first_invalid_entry is not None
            else None
        )
        nodes = []
        edges = []
        previous_recorded_hash = GENESIS_PREVIOUS_HASH

        for expected_sequence, entry in enumerate(entries, start=1):
            sequence = entry.get("sequence", expected_sequence)
            transaction_id = str(entry.get("transaction_id", "Unknown transaction"))
            recorded_hash = entry.get("entry_hash")
            recorded_previous_hash = entry.get("previous_hash")
            expected_hash = compute_chain_entry_hash(entry)
            entry_valid = (
                isinstance(recorded_hash, str)
                and hmac.compare_digest(recorded_hash.lower(), expected_hash)
            )
            link_valid = recorded_previous_hash == previous_recorded_hash
            is_first_invalid = invalid_sequence == expected_sequence
            validity = "invalid" if is_first_invalid else "valid"
            if invalid_sequence is not None and expected_sequence > invalid_sequence:
                validity = "unchecked"

            nodes.append(
                IntegrityGraphNode(
                    sequence=expected_sequence,
                    transaction_id=transaction_id,
                    hash_preview=self._hash_preview(recorded_hash),
                    previous_hash_preview=self._hash_preview(recorded_previous_hash),
                    entry_hash=str(recorded_hash or ""),
                    previous_hash=str(recorded_previous_hash or ""),
                    entry_valid=entry_valid,
                    link_valid=link_valid,
                    validity=validity,
                    failure_type=failure_type if is_first_invalid else None,
                )
            )

            if expected_sequence > 1:
                edges.append(
                    IntegrityGraphEdge(
                        source_sequence=expected_sequence - 1,
                        target_sequence=expected_sequence,
                        valid=link_valid and validity != "invalid",
                    )
                )

            if isinstance(recorded_hash, str):
                previous_recorded_hash = recorded_hash

        return IntegrityGraphResult(
            valid=integrity.valid,
            total_entries=len(entries),
            entries_checked=integrity.entries_checked,
            ledger_head_hash=integrity.ledger_head_hash,
            first_invalid_sequence=invalid_sequence,
            failure_type=failure_type,
            nodes=nodes,
            edges=edges,
        )

    @staticmethod
    def _hash_preview(value):
        if not isinstance(value, str) or not value:
            return "Unavailable"
        if len(value) <= 16:
            return value
        return f"{value[:8]}...{value[-8:]}"
