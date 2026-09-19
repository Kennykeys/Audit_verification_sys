# Security Configuration

Phase 10 configures CORS origins, trusted hosts, response security headers, request-size bounds, request correlation identifiers, and in-process rate limits through environment variables.

## Development defaults

The default origins and hosts are limited to localhost, 127.0.0.1, and the test client host. Wildcard origins are rejected when configuration is loaded.

## Environment variables

- `AUDIT_ALLOWED_ORIGINS`: comma-separated browser origins.
- `AUDIT_TRUSTED_HOSTS`: comma-separated HTTP Host values.
- `AUDIT_MAX_REQUEST_BODY_BYTES`: maximum accepted request body size.
- `AUDIT_LOGIN_RATE_LIMIT`: login attempts per window.
- `AUDIT_MUTATION_RATE_LIMIT`: write requests per window.
- `AUDIT_RATE_LIMIT_WINDOW_SECONDS`: rate-limit window.
- `AUDIT_HTTPS_REDIRECT`: enable only when direct HTTPS handling is intended.

## Proxy and HTTPS assumptions

Forwarded client-address headers are not trusted by this phase. Rate limiting uses the directly connected client address. A reverse proxy must not be treated as trusted unless a later explicit boundary defines trusted proxy addresses and forwarded-header processing. Production deployment must terminate HTTPS at a documented trusted boundary. Enable application HTTPS redirection only when it cannot conflict with proxy termination.

## Limits

The in-process rate limiter is appropriate for the current single-process deployment. Multi-process or horizontally scaled deployment requires a shared rate-limit store. Request-size enforcement rejects declared oversized payloads before endpoint processing.

## Error and header behavior

Security headers and `X-Request-ID` are applied to successful and failed responses. Validation detail remains available in a normalized JSON envelope. Unhandled exceptions return a controlled message without stack traces.
