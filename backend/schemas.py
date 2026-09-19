from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HashableTransactionPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction_id: str = Field(min_length=1)
    amount: Decimal
    member_id: str = Field(min_length=1)
    description: str
    timestamp: datetime
    method: str
    network: str | None = None
    phone_number: str | None = None


class HashLinkedLedgerRecord(HashableTransactionPayload):
    model_config = ConfigDict(extra="allow")

    schema_version: int = Field(default=1, ge=1)
    sequence: int = Field(ge=1)
    previous_hash: str = Field(min_length=64, max_length=64)
    entry_hash: str = Field(min_length=64, max_length=64)

class EntryIntegrityResult(BaseModel):
    sequence: int | None = None
    transaction_id: str | None = None
    valid: bool
    failure_type: str | None = None
    expected_value: str | None = None
    recorded_value: str | None = None


class LedgerIntegrityResult(BaseModel):
    valid: bool
    total_entries: int = Field(ge=0)
    entries_checked: int = Field(ge=0)
    first_invalid_entry: EntryIntegrityResult | None = None
    ledger_head_hash: str | None = None
