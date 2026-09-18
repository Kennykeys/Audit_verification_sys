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
