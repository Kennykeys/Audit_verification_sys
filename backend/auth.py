from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import threading

import bcrypt
from fastapi import HTTPException, status

from backend.config import Settings
from backend.schemas import AuthenticatedPrincipal

UNIFORM_LOGIN_FAILURE = "Invalid username or password"
DUMMY_PASSWORD_HASH = b"$2b$12$C6UzMDM.H6dfI/f/IKcEe.ou7Q7khtkshTnVh2zudx8iOgYB1N3mK"

@dataclass(frozen=True)
class SessionRecord:
    principal: AuthenticatedPrincipal
    issued_at: datetime
    expires_at: datetime

class AuthenticationService:
    def __init__(self, settings: Settings, clock=None):
        self.settings = settings
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sessions = {}
        self._lock = threading.RLock()

    @staticmethod
    def _digest(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _unauthorized():
        return HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})

    @staticmethod
    def _token(authorization):
        if not authorization:
            raise AuthenticationService._unauthorized()
        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token.strip():
            raise AuthenticationService._unauthorized()
        return token.strip()

    def login(self, username, password):
        configured = self.settings.admin_username
        username_matches = bool(configured) and secrets.compare_digest(username, configured)
        candidate = self.settings.admin_password_hash.encode("utf-8") if username_matches and self.settings.admin_password_hash else DUMMY_PASSWORD_HASH
        try:
            password_matches = bcrypt.checkpw(password.encode("utf-8"), candidate)
        except ValueError:
            password_matches = False
        if not username_matches or not password_matches or not self.settings.admin_password_hash:
            raise HTTPException(status_code=401, detail=UNIFORM_LOGIN_FAILURE)
        issued_at = self._clock()
        expires_at = issued_at + timedelta(seconds=self.settings.session_ttl_seconds)
        principal = AuthenticatedPrincipal(username=configured, role=self.settings.admin_role)
        raw_token = secrets.token_urlsafe(48)
        with self._lock:
            self._sessions[self._digest(raw_token)] = SessionRecord(principal, issued_at, expires_at)
        return raw_token, principal, expires_at

    def authenticate(self, authorization):
        digest = self._digest(self._token(authorization))
        with self._lock:
            record = self._sessions.get(digest)
            if record is None:
                raise self._unauthorized()
            if self._clock() >= record.expires_at:
                self._sessions.pop(digest, None)
                raise self._unauthorized()
            return record.principal

    def logout(self, authorization):
        digest = self._digest(self._token(authorization))
        with self._lock:
            if self._sessions.pop(digest, None) is None:
                raise self._unauthorized()

    def require_role(self, authorization, required_role):
        principal = self.authenticate(authorization)
        if principal.role != required_role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return principal
