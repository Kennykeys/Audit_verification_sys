from concurrent.futures import ThreadPoolExecutor

from backend.integrity import verify_chain_links
from backend.repository import AuditLedgerRepository


def sample_entry(index):
    return {"transaction_id": f"TX-{index}", "amount": index + 1, "member_id": "M001", "description": "Concurrent", "created_at": "2026-09-19T12:00:00Z", "method": "Admin", "network": None, "phone_number": None}


def test_simultaneous_appends_do_not_lose_entries(tmp_path):
    ledger_path = tmp_path / "audit_log.json"
    ledger_path.write_text("[]\n", encoding="utf-8")
    repository = AuditLedgerRepository(ledger_path)
    entry_count = 20
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda index: repository.append_entry(sample_entry(index)), range(entry_count)))
    entries = repository.load_entries()
    assert len(results) == entry_count
    assert len(entries) == entry_count
    assert {entry["transaction_id"] for entry in entries} == {f"TX-{index}" for index in range(entry_count)}
    assert [entry["sequence"] for entry in entries] == list(range(1, entry_count + 1))
    assert verify_chain_links(entries)
