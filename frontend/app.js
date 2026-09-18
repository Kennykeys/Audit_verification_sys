// Verify transaction form
document.getElementById("verifyForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = document.getElementById("verify_id").value;

  try {
    const res = await fetch(`${window.AUDIT_APP_CONFIG.apiBaseUrl}/verify/${id}`);
    const result = await res.json();
    document.getElementById("verifyResponse").textContent = JSON.stringify(result, null, 2);
  } catch (err) {
    document.getElementById("verifyResponse").textContent = "Error: " + err.message;
  }
});

// Mobile Money simulation
function showPaymentOptions() {
  document.getElementById("paymentSection").style.display = "block";
}

async function simulatePayment() {
  const network = document.getElementById("network").value;
  const number = document.getElementById("phoneNumber").value.trim();
  const amount = parseFloat(document.getElementById("mobileAmount").value);
  const member = document.getElementById("mobileMember").value;
  const responseBox = document.getElementById("paymentResponse");

  if (!network) {
    responseBox.textContent = "Please select a network.";
    return;
  }

  if (!/^\d{10}$/.test(number)) {
    responseBox.textContent = "Invalid number: must be 10 digits.";
    return;
  }

  let valid = false;
  if (network === "airtel") {
    valid = /^(070|075|074|02)\d{7}$/.test(number);
  } else if (network === "mtn") {
    valid = /^(077|076|078)\d{7}$/.test(number);
  }

  if (!valid) {
    responseBox.textContent = "❌ Invalid " + network.toUpperCase() + " number.";
    return;
  }

  // Build transaction data
  const data = {
    transaction_id: "MM" + Date.now(),
    amount: amount,
    member_id: member,
    description: `Mobile Money Payment (${network.toUpperCase()})`
  };

  try {
    const res = await fetch(`${window.AUDIT_APP_CONFIG.apiBaseUrl}/record_mobile`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data)
    });
    const result = await res.json();
    responseBox.textContent = "✅ " + network.toUpperCase() + " number accepted. PIN prompt will appear on your phone (simulation).\n\n" +
      JSON.stringify(result, null, 2);
  } catch (err) {
    responseBox.textContent = "Error recording transaction: " + err.message;
  }
}
