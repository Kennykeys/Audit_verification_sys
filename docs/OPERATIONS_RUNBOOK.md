# Operations Runbook

## Operational signals

The service emits one-line JSON events with timestamp, severity, event name, request identifier, HTTP method, route, status code, and request duration. Passwords, tokens, authorization headers, member identifiers, phone numbers, and transaction descriptions are redacted.

## Health endpoints

- `GET /health/live` confirms only that the process can answer requests. It does not read or mutate the ledger.
- `GET /health/ready` performs a read-only repository and chain-integrity check. A valid ledger returns HTTP 200. Invalid or unavailable storage returns HTTP 503 with minimal public detail.

## Alert signals

Investigate repeated `authentication_failed`, `access_denied`, HTTP 429 responses, readiness failures, integrity failures, HTTP 500 responses, or sustained latency growth. Correlate events with the `X-Request-ID` response header.

## Recovery actions

1. Stop mutation traffic when readiness reports an invalid ledger.
2. Preserve the active ledger and lock metadata before investigation.
3. Compare the active ledger against the verified pre-chain backup and recent trusted backups.
4. Run the comprehensive quality gate and integrity verification against a copied ledger.
5. Restore only from a verified backup following administrator review.

## Privacy and security

Never log request bodies, passwords, bearer tokens, full authorization headers, complete transaction payloads, phone numbers, or member identifiers. Public health responses must not expose filesystem paths, hashes, credentials, configuration values, or ledger records.

## Proxy and deployment assumptions

Request identifiers supplied by clients are accepted only when they satisfy the existing security-boundary format. Proxy trust is not enabled by this phase. HTTPS termination and forwarded-header trust require an explicitly configured deployment boundary.
