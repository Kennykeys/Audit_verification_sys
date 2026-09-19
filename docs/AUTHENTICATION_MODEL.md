# Server-Side Authentication and Authorization Model

## Status

This document defines the Phase 9 authentication architecture before implementation. It contains no secret values, accepted passwords, or production credentials.

## Selected model

The application will use opaque, cryptographically random bearer session tokens. The backend will store only SHA-256 token digests in memory. Clients will send `Authorization: Bearer <token>`.

The current deployment assumes one backend process. A restart invalidates all sessions. Horizontal scaling will require a shared revocable session store.

## Administrator configuration

Runtime configuration will be supplied through environment variables:

- `AUDIT_ADMIN_USERNAME`
- `AUDIT_ADMIN_PASSWORD_HASH`, containing a bcrypt verifier
- `AUDIT_ADMIN_ROLE`, defaulting to `administrator`
- `AUDIT_SESSION_TTL_SECONDS`

Only development placeholders and hash-generation guidance belong in `.env.example`. Plaintext passwords must not be committed, logged, documented, or persisted.

## Password verification

Password verification will use `bcrypt.checkpw`. A valid dummy bcrypt hash will be checked when the username does not match, so authentication failures still use the established password-verification primitive. Failures will use one uniform response and will not reveal whether an account exists.

## Session lifecycle

A successful login creates a bounded session containing the token digest, principal name, administrator role, issue time, and expiration time. Expired sessions are deleted when checked. `POST /auth/logout` revokes the presented session. Raw tokens and passwords are never stored by the backend.

## Authentication endpoints

- `POST /auth/login` validates environment-configured verifier material and issues an opaque token.
- `GET /auth/me` returns the `AuthenticatedPrincipal` for a valid session.
- `POST /auth/logout` revokes the current session.

Missing, invalid, expired, or revoked credentials return `401`. An authenticated principal without the required role returns `403`.

## Authorization boundary

The `administrator` role is required for:

- `GET /transactions`
- `POST /record`
- `POST /record_mobile`

These public read-only routes remain unauthenticated:

- `GET /verify/{transaction_id}`
- `GET /integrity`
- `GET /integrity/graph`

## Frontend behavior

`frontend/login.js` sends credentials only to `/auth/login`. The password is read only for submission and is not persisted. The bearer token is held in `sessionStorage`. `frontend/js/api.js` attaches the token to protected requests. A `401` or `403` clears the token and redirects administrative pages to `login.html`. Logout calls `/auth/logout`, clears local session state, and redirects.

## Threat boundaries

This phase addresses hard-coded browser credentials, unauthenticated administrative APIs, expiration, logout, role checks, uniform login failure responses, and removal of accepted plaintext credential pairs.

This phase does not claim to implement TLS termination, CORS hardening, rate limiting, security headers, distributed session persistence, user provisioning, or password recovery. Those controls remain queued.

## Legacy authentication module

`backend/auth_backend.py` is a separate FastAPI application that is not mounted in `backend/main.py`, but the repository contains an accepted administrator credential branch exercised by tests. Phase 9 cannot satisfy the requirement that no accepted credential pair remains committed unless modification authority is expanded to include `backend/auth_backend.py` and its affected test `tests/backend/test_transaction_api_integrity.py`, or a repository administrator explicitly excludes that legacy application from the security scope.

The professional recommendation is to authorize the minimal removal of the legacy accepted credential behavior.

## Testing requirements

Tests must cover successful login, uniform login failure, missing token, invalid token, expired token, revoked token, insufficient role, protected administrative routes, public verification routes, frontend redirect behavior, and absence of accepted username or password literals in frontend source.
