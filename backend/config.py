import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
DEFAULT_LEDGER_PATH = BACKEND_ROOT / "audit_repo" / "audit_log.json"


@dataclass(frozen=True)
class Settings:
    ledger_path: Path

    @classmethod
    def from_environment(cls):
        configured = os.getenv("AUDIT_LEDGER_PATH")
        ledger_path = Path(configured).expanduser() if configured else DEFAULT_LEDGER_PATH
        return cls(ledger_path=ledger_path.resolve(strict=False))
