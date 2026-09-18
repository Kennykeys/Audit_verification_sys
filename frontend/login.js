"use strict";

const loginForm = document.getElementById("loginForm");
const loginResponse = document.getElementById("loginResponse");

function apiUrl(route) {
  return `${window.AUDIT_APP_CONFIG.apiBaseUrl}${route}`;
}

async function readPayload(response) {
  try {
    return await response.json();
  } catch (_error) {
    return {};
  }
}

function renderAdminVerification(user, generatedCode) {
  window.AuditUi.clearElement(loginResponse);
  const message = document.createElement("p");
  message.textContent = "Enter the administrator verification code.";
  const simulation = document.createElement("p");
  simulation.textContent = `Generated code for this simulation: ${generatedCode}`;
  const codeInput = document.createElement("input");
  codeInput.type = "text";
  codeInput.id = "admin2faInput";
  codeInput.placeholder = "Enter verification code";
  codeInput.autocomplete = "one-time-code";
  const verifyButton = document.createElement("button");
  verifyButton.type = "button";
  verifyButton.textContent = "Verify";
  loginResponse.append(message, simulation, codeInput, verifyButton);
  verifyButton.addEventListener("click", async () => {
    const code = codeInput.value.trim();
    if (!code) {
      window.AuditUi.setStatus(loginResponse, "Enter the verification code.", "error");
      return;
    }
    const response = await fetch(apiUrl("/admin_verify"), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({member_id: user, code: code})
    });
    const payload = await readPayload(response);
    if (!response.ok) {
      window.AuditUi.setStatus(loginResponse, payload.detail || "Verification failed.", "error");
      return;
    }
    sessionStorage.setItem("isAdminLoggedIn", "true");
    window.location.href = "transactions.html";
  });
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const user = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const route = user === "admin" ? "/admin_login" : "/member_login";
  try {
    const response = await fetch(apiUrl(route), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({member_id: user, password: password})
    });
    const payload = await readPayload(response);
    if (!response.ok) {
      window.AuditUi.setStatus(loginResponse, payload.detail || "Login failed.", "error");
      return;
    }
    if (payload.step === "2fa_required") {
      renderAdminVerification(user, payload.code);
      return;
    }
    sessionStorage.setItem("memberLoggedIn", "true");
    sessionStorage.setItem("memberId", user);
    sessionStorage.setItem("logoutAt", String(Date.now() + window.AUDIT_APP_CONFIG.memberSessionDurationMs));
    window.location.href = "index.html";
  } catch (_error) {
    window.AuditUi.setStatus(loginResponse, "The authentication service is unavailable.", "error");
  }
});
