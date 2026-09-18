document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const memberId = document.getElementById("memberId").value.trim();
  const password = document.getElementById("password").value.trim();
  const responseBox = document.getElementById("loginResponse");

  try {
    const res = await fetch("http://127.0.0.1:8000/member_login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ member_id: memberId, password: password })
    });

    if (!res.ok) {
      let errorMsg;
      try {
        const error = await res.json();
        errorMsg = error.detail;
      } catch {
        errorMsg = await res.text();
      }
      responseBox.textContent = "❌ " + errorMsg; // shows attempts or lockout message
      return;
    }

    const result = await res.json();
    responseBox.textContent = "✅ " + result.message;

    // Save login state
    sessionStorage.setItem("memberLoggedIn", "true");
    sessionStorage.setItem("memberId", memberId);

    // Set auto logout after 30 minutes
    const logoutTime = Date.now() + (30 * 60 * 1000);
    sessionStorage.setItem("logoutAt", logoutTime);

    window.location.href = "index.html";
  } catch (err) {
    responseBox.textContent = "❌ Error: " + err.message;
  }
});

// ✅ Show Forgot Password form when button is clicked
document.getElementById("showForgotPassword").addEventListener("click", () => {
  document.getElementById("forgotPasswordForm").style.display = "block";
});

// ✅ Forgot Password handler
document.getElementById("forgotPasswordForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = document.getElementById("forgotEmail").value.trim();
  const responseBox = document.getElementById("forgotPasswordResponse");

  try {
    const res = await fetch("http://127.0.0.1:8000/forgot_password", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ email: email })
    });

    const result = await res.json();
    if (!res.ok) {
      responseBox.textContent = "❌ " + (result.detail || JSON.stringify(result));
      return;
    }
    responseBox.textContent = "✅ " + result.message;
  } catch (err) {
    responseBox.textContent = "❌ Error: " + err.message;
  }
});

// ✅ Auto logout enforcement (runs on every page load)
window.onload = () => {
  const logoutAt = sessionStorage.getItem("logoutAt");
  if (logoutAt && Date.now() > logoutAt) {
    alert("Session expired. Please log in again.");
    sessionStorage.clear();
    window.location.href = "member_login.html";
  }
};
// ---------------- TRANSACTION VERIFICATION ----------------

document.getElementById("verifyForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const txId = document.getElementById("verify_id").value.trim();
  const responseBox = document.getElementById("verifyResponse");

  try {
    const res = await fetch(`http://127.0.0.1:8000/verify/${txId}`);
    if (!res.ok) {
      const error = await res.json();
      responseBox.textContent = "❌ " + (error.detail || JSON.stringify(error));
      return;
    }

    const result = await res.json();
    responseBox.textContent = "✅ Transaction verification:\n" + JSON.stringify(result, null, 2);
  } catch (err) {
    responseBox.textContent = "❌ Error: " + err.message;
  }
});