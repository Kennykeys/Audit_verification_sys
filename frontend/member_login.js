"use strict";

const memberLoginForm = document.getElementById("loginForm");
const memberLoginResponse = document.getElementById("loginResponse");

memberLoginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const memberId = document.getElementById("memberId").value.trim();
  const password = document.getElementById("password").value;
  try {
    const response = await fetch(`${window.AUDIT_APP_CONFIG.apiBaseUrl}/member_login`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({member_id: memberId, password: password})
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch (_error) {
      payload = {};
    }
    if (!response.ok) {
      window.AuditUi.setStatus(memberLoginResponse, payload.detail || "Login failed.", "error");
      return;
    }
    sessionStorage.setItem("memberLoggedIn", "true");
    sessionStorage.setItem("memberId", memberId);
    sessionStorage.setItem("logoutAt", String(Date.now() + window.AUDIT_APP_CONFIG.memberSessionDurationMs));
    window.location.href = "index.html";
  } catch (_error) {
    window.AuditUi.setStatus(memberLoginResponse, "The authentication service is unavailable.", "error");
  }
});
