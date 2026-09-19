'use strict';

window.AUDIT_APP_CONFIG = Object.freeze({
  apiBaseUrl: window.AUDIT_API_BASE_URL || "http://127.0.0.1:8000",
  memberSessionDurationMs: 30 * 60 * 1000,
  isDemoData: false,
  integrityStatusText: "Deterministic SHA-256 verification available",
});
