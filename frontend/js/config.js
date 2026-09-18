'use strict';

window.AUDIT_APP_CONFIG = Object.freeze({
  apiBaseUrl: "http://127.0.0.1:8010",
  memberSessionDurationMs: 30 * 60 * 1000,
  isDemoData: true,
  demoSummary: Object.freeze({
    recordedTransactions: 2,
    verifiedTransactions: 2,
    integrityStatus: "Deterministic SHA-256 verification available"
  })
});
