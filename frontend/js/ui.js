'use strict';

(function initializeAuditUi(globalObject) {
  function getElement(elementOrId) {
    if (typeof elementOrId === "string") {
      return document.getElementById(elementOrId);
    }
    return elementOrId;
  }

  function clearElement(elementOrId) {
    const element = getElement(elementOrId);
    if (!element) return;
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }
  }

  function setStatus(elementOrId, message, state) {
    const element = getElement(elementOrId);
    if (!element) return;
    element.textContent = message || "";
    element.dataset.state = state || "info";
    element.hidden = !message;
  }

  function setBusy(buttonOrId, isBusy, busyLabel) {
    const button = getElement(buttonOrId);
    if (!button) return;
    if (!button.dataset.defaultLabel) {
      button.dataset.defaultLabel = button.textContent;
    }
    button.disabled = Boolean(isBusy);
    button.setAttribute("aria-busy", String(Boolean(isBusy)));
    button.textContent = isBusy
      ? busyLabel || "Please wait..."
      : button.dataset.defaultLabel;
  }

  function createCell(value, className) {
    const cell = document.createElement("td");
    cell.textContent = value === null || value === undefined || value === ""
      ? "Not available"
      : String(value);
    if (className) cell.className = className;
    return cell;
  }

  function createEmptyRow(columnCount, message) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = columnCount;
    cell.className = "table-empty";
    cell.textContent = message;
    row.appendChild(cell);
    return row;
  }

  function formatAmount(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return "Not available";
    return new Intl.NumberFormat("en-UG", {
      style: "currency",
      currency: "UGX",
      maximumFractionDigits: 0
    }).format(amount);
  }

  globalObject.AuditUi = Object.freeze({
    clearElement,
    setStatus,
    setBusy,
    createCell,
    createEmptyRow,
    formatAmount
  });
})(window);
