'use strict';

const transactionTableBody = document.getElementById('transactionsTableBody');
const transactionForm = document.getElementById('addTransactionForm');
const transactionResponse = document.getElementById('transactionsResponse');
const transactionSubmitButton = transactionForm.querySelector('button[type="submit"]');

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
  row.appendChild(window.AuditUi.createCell(transaction.hash, 'hash-cell'));
  transactionTableBody.appendChild(row);
}

async function readResponse(response) {
  try {
    return await response.json();
  } catch (_error) {
    return {};
  }
}

async function loadTransactions() {
  renderTableState('Loading transactions...');

  try {
    const response = await fetch(`${window.AUDIT_APP_CONFIG.apiBaseUrl}/transactions`);
    const payload = await readResponse(response);

    if (!response.ok) {
      renderTableState(payload.detail || 'Transactions could not be loaded.');
      return;
    }

    const transactions = Array.isArray(payload.transactions) ? payload.transactions : [];
    window.AuditUi.clearElement(transactionTableBody);

    if (transactions.length === 0) {
      renderTableState('No transactions have been recorded yet.');
      return;
    }

    transactions.forEach(renderTransaction);
  } catch (_error) {
    renderTableState('The transaction service is unavailable. Try again later.');
  }
}

transactionForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  window.AuditUi.setStatus(transactionResponse, 'Recording transaction...', 'info');
  window.AuditUi.setBusy(transactionSubmitButton, true, 'Recording...');

  const transaction = {
    transaction_id: document.getElementById('transactionId').value.trim(),
    amount: Number(document.getElementById('amount').value),
    member_id: document.getElementById('memberId').value.trim(),
    description: document.getElementById('description').value.trim(),
    method: 'manual'
  };

  try {
    const response = await fetch(`${window.AUDIT_APP_CONFIG.apiBaseUrl}/transactions`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(transaction)
    });
    const payload = await readResponse(response);

    if (!response.ok) {
      window.AuditUi.setStatus(
        transactionResponse,
        payload.detail || 'The transaction could not be recorded.',
        'error'
      );
      return;
    }

    transactionForm.reset();
    window.AuditUi.setStatus(transactionResponse, 'Transaction recorded successfully.', 'success');
    await loadTransactions();
  } catch (_error) {
    window.AuditUi.setStatus(
      transactionResponse,
      'The transaction service is unavailable. Try again later.',
      'error'
    );
  } finally {
    window.AuditUi.setBusy(transactionSubmitButton, false);
  }
});

document.addEventListener('DOMContentLoaded', loadTransactions);
