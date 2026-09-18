from decimal import Decimal

from backend.schemas import HashableTransactionPayload


def test_hashable_transaction_payload_normalizes_decimal():
    payload = HashableTransactionPayload(
        transaction_id="TX-001",
        amount="50000.00",
        member_id="M001",
        description="Loan repayment",
        timestamp="2026-09-14T15:30:00Z",
        method="manual",
    )
    assert payload.amount == Decimal("50000.00")
    assert payload.network is None
    assert payload.phone_number is None
