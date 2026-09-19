'use strict';

(function initializeDashboard() {
  const verifyForm = document.getElementById('verifyForm');
  const verifyResponse = document.getElementById('verifyResponse');
  const mobileForm = document.getElementById('mobileMoneyForm');
  const mobileResponse = document.getElementById('mobileMoneyResponse');
  const mobileSubmitButton = mobileForm.querySelector('button[type="submit"]');
  const recordingSummary = document.getElementById('recordingSummary');

  function validationMessage(error, fallback) {
    const detail = error.payload && error.payload.detail;
    if (!Array.isArray(detail)) return error.message || fallback;
    return detail.map((item) => {
      const location = Array.isArray(item.loc) ? item.loc : [];
      const field = location.length ? location[location.length - 1] : 'field';
      return `${field}: ${item.msg || 'Invalid value'}`;
    }).join('; ');
  }

  async function refreshSummary() {
    const payload = await window.AuditApi.request('/transactions');
    const transactions = Array.isArray(payload.transactions) ? payload.transactions : [];
    const totalAmount = transactions.reduce((sum, transaction) => {
      const amount = Number(transaction.amount);
      return Number.isFinite(amount) ? sum + amount : sum;
    }, 0);
    window.AuditUi.clearElement(recordingSummary);
    const count = document.createElement('strong');
    count.textContent = `Recorded transactions: ${transactions.length}`;
    const amount = document.createElement('span');
    amount.textContent = `Total recorded value: ${window.AuditUi.formatAmount(totalAmount)}`;
    recordingSummary.appendChild(count);
    recordingSummary.appendChild(amount);
  }

  verifyForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const transactionId = document.getElementById('verify_id').value.trim();
    const button = verifyForm.querySelector('button[type="submit"]');
    window.AuditUi.setBusy(button, true, 'Verifying...');
    window.AuditUi.setStatus(verifyResponse, 'Verifying transaction...', 'info');
    try {
      const result = await window.AuditApi.request(`/verify/${encodeURIComponent(transactionId)}`);
      window.AuditUi.clearElement(verifyResponse);
      verifyResponse.dataset.state = result.verified ? "success" : "error";
      const heading = document.createElement("strong");
      heading.textContent = result.verified ? "Verified transaction" : "Verification failed";
      const record = document.createElement("p");
      record.textContent = `Record hash: ${result.record_valid ? "valid" : "invalid"}`;
      const context = document.createElement("p");
      context.textContent = `Ledger context: ${result.ledger_context_valid ? "valid" : "invalid"}`;
      const failure = document.createElement("p");
      failure.textContent = `Failure type: ${result.failure_type || "None"}`;
      verifyResponse.append(heading,record,context,failure);
    } catch (error) {
      window.AuditUi.setStatus(verifyResponse, error.message || 'Verification failed.', 'error');
    } finally {
      window.AuditUi.setBusy(button, false);
    }
  });

  mobileForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    window.AuditUi.setBusy(mobileSubmitButton, true, 'Recording simulation...');
    window.AuditUi.setStatus(mobileResponse, 'Validating and recording mobile-money simulation...', 'info');
    const payload = {
      network: document.getElementById('network').value,
      phone_number: document.getElementById('phoneNumber').value.trim(),
      amount: Number(document.getElementById('mmAmount').value),
      member_id: document.getElementById('mmMemberId').value.trim(),
      description: document.getElementById('mmDescription').value
    };
    try {
      const result = await window.AuditApi.request('/record_mobile', { method: 'POST', body: payload });
      window.AuditUi.setStatus(
        mobileResponse,
        `Simulation recorded successfully as ${result.transaction.transaction_id}.`,
        'success'
      );
      mobileForm.reset();
      await refreshSummary();
    } catch (error) {
      window.AuditUi.setStatus(
        mobileResponse,
        validationMessage(error, 'The simulation could not be recorded.'),
        'error'
      );
    } finally {
      window.AuditUi.setBusy(mobileSubmitButton, false);
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    refreshSummary().catch(() => {
      window.AuditUi.setStatus(recordingSummary, 'Ledger summary is currently unavailable.', 'error');
    });
  });
})();
