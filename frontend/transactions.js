'use strict';

(function initializeTransactionsPage() {
  const transactionTableBody = document.getElementById('transactionsTableBody');
  const transactionForm = document.getElementById('addTransactionForm');
  const transactionResponse = document.getElementById('transactionsResponse');
  const transactionSubmitButton = transactionForm.querySelector('button[type="submit"]');
  const transactionSummary = document.getElementById('transactionSummary');

  function installLogoutButton() {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Logout';
    button.addEventListener('click', async () => {
      try { await window.AuditApi.request('/auth/logout', { method: 'POST', redirectOnAuthFailure: false }); }
      finally { window.AuditApi.clearToken(); window.AuditApi.redirectToLogin(); }
    });
    transactionForm.parentElement.insertBefore(button, transactionForm);
  }

  function renderTableState(message) {
    window.AuditUi.clearElement(transactionTableBody);
    transactionTableBody.appendChild(window.AuditUi.createEmptyRow(9, message));
  }

  function renderTransaction(transaction) {
    const row = document.createElement('tr');
    row.appendChild(window.AuditUi.createCell(transaction.transaction_id));
    row.appendChild(window.AuditUi.createCell(window.AuditUi.formatAmount(transaction.amount)));
    row.appendChild(window.AuditUi.createCell(transaction.member_id));
    row.appendChild(window.AuditUi.createCell(transaction.description));
    row.appendChild(window.AuditUi.createCell(transaction.date_time || transaction.created_at));
    row.appendChild(window.AuditUi.createCell(transaction.method));
    row.appendChild(window.AuditUi.createCell(transaction.network));
    row.appendChild(window.AuditUi.createCell(transaction.phone_number));
    row.appendChild(window.AuditUi.createCell(transaction.entry_hash || transaction.hash, 'hash-cell'));
    transactionTableBody.appendChild(row);
  }

  function renderSummary(transactions) {
    const totalAmount = transactions.reduce((sum, transaction) => {
      const amount = Number(transaction.amount);
      return Number.isFinite(amount) ? sum + amount : sum;
    }, 0);
    window.AuditUi.clearElement(transactionSummary);
    const count = document.createElement('strong');
    count.textContent = `Recorded transactions: ${transactions.length}`;
    const amount = document.createElement('span');
    amount.textContent = `Total recorded value: ${window.AuditUi.formatAmount(totalAmount)}`;
    transactionSummary.appendChild(count);
    transactionSummary.appendChild(amount);
  }

  async function loadTransactions() {
    renderTableState('Loading transactions...');
    const payload = await window.AuditApi.request('/transactions');
    const transactions = Array.isArray(payload.transactions) ? payload.transactions : [];
    renderSummary(transactions);
    window.AuditUi.clearElement(transactionTableBody);
    if (transactions.length === 0) {
      renderTableState('No transactions have been recorded yet.');
      return;
    }
    transactions.forEach(renderTransaction);
  }

  function validationMessage(error) {
    const detail = error.payload && error.payload.detail;
    if (!Array.isArray(detail)) return error.message || 'The transaction could not be recorded.';
    return detail.map((item) => {
      const location = Array.isArray(item.loc) ? item.loc : [];
      const field = location.length ? location[location.length - 1] : 'field';
      return `${field}: ${item.msg || 'Invalid value'}`;
    }).join('; ');
  }

  transactionForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    window.AuditUi.setBusy(transactionSubmitButton, true, 'Recording...');
    window.AuditUi.setStatus(transactionResponse, 'Validating and recording transaction...', 'info');
    const transaction = {
      transaction_id: document.getElementById('transactionId').value.trim(),
      amount: Number(document.getElementById('amount').value),
      member_id: document.getElementById('memberId').value.trim(),
      description: document.getElementById('description').value.trim()
    };
    try {
      const result = await window.AuditApi.request('/record', { method: 'POST', body: transaction });
      transactionForm.reset();
      window.AuditUi.setStatus(
        transactionResponse,
        `Transaction ${result.transaction.transaction_id} recorded successfully.`,
        'success'
      );
      await loadTransactions();
    } catch (error) {
      window.AuditUi.setStatus(transactionResponse, validationMessage(error), 'error');
    } finally {
      window.AuditUi.setBusy(transactionSubmitButton, false);
    }
  });

  document.addEventListener('DOMContentLoaded', async () => {
    try { await window.AuditApi.request('/auth/me'); installLogoutButton(); await loadTransactions(); }
    catch (error) { renderTableState('Administrator authentication is required.'); window.AuditUi.setStatus(transactionResponse, error.message || 'Authentication failed.', 'error'); }
  });
})();
