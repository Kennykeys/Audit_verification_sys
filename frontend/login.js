"use strict";
const loginForm = document.getElementById("loginForm");
const loginResponse = document.getElementById("loginResponse");
const loginButton = loginForm.querySelector('button[type="submit"]');
loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  window.AuditUi.setBusy(loginButton, true, "Signing in...");
  window.AuditUi.setStatus(loginResponse, "Validating administrator credentials...", "info");
  const passwordInput = document.getElementById("password");
  try {
    const payload = await window.AuditApi.request("/auth/login", { method: "POST", redirectOnAuthFailure: false, body: { username: document.getElementById("username").value.trim(), password: passwordInput.value } });
    window.AuditApi.setToken(payload.access_token);
    passwordInput.value = "";
    window.location.href = "transactions.html";
  } catch (error) {
    passwordInput.value = "";
    window.AuditUi.setStatus(loginResponse, error.message || "Login failed.", "error");
  } finally {
    window.AuditUi.setBusy(loginButton, false);
  }
});
