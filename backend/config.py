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
    allowed_origins: tuple[str, ...] = ("http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5500", "http://127.0.0.1:5500")
    trusted_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")
    max_request_body_bytes: int = 65536
    login_rate_limit: int = 5
    mutation_rate_limit: int = 30
    rate_limit_window_seconds: int = 60
    https_redirect: bool = False
    log_level: str = "INFO"

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
        allowed_origins = tuple(value.strip() for value in os.getenv("AUDIT_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5500,http://127.0.0.1:5500").split(",") if value.strip())
        trusted_hosts = tuple(value.strip() for value in os.getenv("AUDIT_TRUSTED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if value.strip())
        if "*" in allowed_origins:
            raise ValueError("AUDIT_ALLOWED_ORIGINS must not contain a wildcard")
        def positive_integer(name, default):
            try:
                value = int(os.getenv(name, str(default)))
            except ValueError as error:
                raise ValueError(f"{name} must be an integer") from error
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
            return value
        https_redirect = os.getenv("AUDIT_HTTPS_REDIRECT", "false").lower() in {"1", "true", "yes"}
        return cls(
            ledger_path=ledger_path.resolve(strict=False),
            admin_username=os.getenv("AUDIT_ADMIN_USERNAME"),
            admin_password_hash=os.getenv("AUDIT_ADMIN_PASSWORD_HASH"),
            admin_role=os.getenv("AUDIT_ADMIN_ROLE", "administrator"),
            session_ttl_seconds=session_ttl_seconds,
            allowed_origins=allowed_origins,
            trusted_hosts=trusted_hosts,
            max_request_body_bytes=positive_integer("AUDIT_MAX_REQUEST_BODY_BYTES", 65536),
            login_rate_limit=positive_integer("AUDIT_LOGIN_RATE_LIMIT", 5),
            mutation_rate_limit=positive_integer("AUDIT_MUTATION_RATE_LIMIT", 30),
            rate_limit_window_seconds=positive_integer("AUDIT_RATE_LIMIT_WINDOW_SECONDS", 60),
            https_redirect=https_redirect,
            log_level=os.getenv("AUDIT_LOG_LEVEL", "INFO").upper(),
        )
