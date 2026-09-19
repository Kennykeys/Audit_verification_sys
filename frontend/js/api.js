(function () {
  "use strict";

  class ApiError extends Error {
    constructor(message, status, payload) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.payload = payload;
    }
  }

  function getBaseUrl() {
    return window.AUDIT_APP_CONFIG.apiBaseUrl.replace(/\/$/, "");
  }

  async function request(endpoint, options = {}) {
    const controller = new AbortController();
    const timeoutMs = options.timeoutMs || 10000;
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    const requestOptions = {
      method: options.method || "GET",
      headers: { Accept: "application/json", ...(options.headers || {}) },
      signal: controller.signal
    };
    if (options.body !== undefined) {
      requestOptions.headers["Content-Type"] = "application/json";
      requestOptions.body = JSON.stringify(options.body);
    }
    try {
      const response = await fetch(`${getBaseUrl()}${endpoint}`, requestOptions);
      let payload = {};
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        payload = await response.json();
      }
      if (!response.ok) {
        const message = typeof payload.detail === "string" ? payload.detail : "The request could not be completed.";
        throw new ApiError(message, response.status, payload);
      }
      return payload;
    } catch (error) {
      if (error.name === "AbortError") {
        throw new ApiError("The request timed out. Try again.", 0, {});
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  window.AuditApi = Object.freeze({ request, ApiError });
})();
