import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
DEFAULT_LEDGER_PATH = BACKEND_ROOT / "audit_repo" / "audit_log.json"


@dataclass(frozen=True)
class Settings:
    ledger_path: Path
    admin_username: str | None = None
    admin_password_hash: str | None = None
    admin_role: str = "administrator"
    session_ttl_seconds: int = 1800

    @classmethod
    def from_environment(cls):
        configured = os.getenv("AUDIT_LEDGER_PATH")
        ledger_path = Path(configured).expanduser() if configured else DEFAULT_LEDGER_PATH
        try:
            session_ttl_seconds = int(os.getenv("AUDIT_SESSION_TTL_SECONDS", "1800"))
        except ValueError as error:
            raise ValueError("AUDIT_SESSION_TTL_SECONDS must be an integer") from error
        if session_ttl_seconds <= 0:
            raise ValueError("AUDIT_SESSION_TTL_SECONDS must be greater than zero")
        return cls(
            ledger_path=ledger_path.resolve(strict=False),
            admin_username=os.getenv("AUDIT_ADMIN_USERNAME"),
            admin_password_hash=os.getenv("AUDIT_ADMIN_PASSWORD_HASH"),
            admin_role=os.getenv("AUDIT_ADMIN_ROLE", "administrator"),
            session_ttl_seconds=session_ttl_seconds,
        )
