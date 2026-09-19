from copy import deepcopy

from fastapi.testclient import TestClient

from backend import main
from backend.integrity import migrate_legacy_ledger
from backend.services.audit_service import AuditService


class StubRepository:
    def __init__(self, entries):
        self.entries = entries

    def load_entries(self):
        return deepcopy(self.entries)


def legacy(identifier, amount=10):
    return {
        "transaction_id": identifier,
        "amount": amount,
        "member_id": "M001",
        "description": "Graph test",
        "created_at": "2026-09-19T12:00:00Z",
        "method": "Admin",
        "network": None,
        "phone_number": None,
    }


def linked_entries():
    return migrate_legacy_ledger([
        legacy("TX-1"),
        legacy("TX-2", 20),
        legacy("TX-3", 30),
    ])


def test_valid_graph_node_and_edge_counts():
    entries = linked_entries()
    result = AuditService(StubRepository(entries)).build_integrity_graph()
    assert result.valid is True
    assert len(result.nodes) == 3
    assert len(result.edges) == 2
    assert result.ledger_head_hash == entries[-1]["entry_hash"]
    assert all(node.validity == "valid" for node in result.nodes)


def test_invalid_metadata_maps_to_correct_node():
    entries = linked_entries()
    entries[1]["amount"] = 99
    result = AuditService(StubRepository(entries)).build_integrity_graph()
    assert result.valid is False
    assert result.first_invalid_sequence == 2
    assert result.nodes[1].validity == "invalid"
    assert result.nodes[1].failure_type == "entry_hash"
    assert result.nodes[2].validity == "unchecked"


def test_empty_graph_is_valid():
    result = AuditService(StubRepository([])).build_integrity_graph()
    assert result.valid is True
    assert result.nodes == []
    assert result.edges == []


def test_graph_endpoint_returns_read_only_graph(monkeypatch):
    entries = linked_entries()
    service = AuditService(StubRepository(entries))
    monkeypatch.setattr(main, "get_audit_service", lambda: service)
    response = TestClient(main.app).get("/integrity/graph")
    assert response.status_code == 200
    assert len(response.json()["nodes"]) == len(entries)
    assert len(response.json()["edges"]) == len(entries) - 1
