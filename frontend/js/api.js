(function () {
  "use strict";
  const TOKEN_KEY = "auditAdminToken";
  class ApiError extends Error { constructor(message, status, payload) { super(message); this.name="ApiError"; this.status=status; this.payload=payload; } }
  function getBaseUrl() { return window.AUDIT_APP_CONFIG.apiBaseUrl.replace(/\/$/, ""); }
  function getToken() { return window.sessionStorage.getItem(TOKEN_KEY); }
  function setToken(token) { window.sessionStorage.setItem(TOKEN_KEY, token); }
  function clearToken() { window.sessionStorage.removeItem(TOKEN_KEY); }
  function redirectToLogin() { if (!window.location.pathname.endsWith("login.html")) window.location.href="login.html"; }
  async function request(endpoint, options={}) {
    const controller=new AbortController(); const timeoutId=window.setTimeout(()=>controller.abort(),options.timeoutMs||10000);
    const requestOptions={method:options.method||"GET",headers:{Accept:"application/json",...(options.headers||{})},signal:controller.signal};
    const token=getToken(); if(token && options.auth!==false) requestOptions.headers.Authorization=`Bearer ${token}`;
    if(options.body!==undefined){requestOptions.headers["Content-Type"]="application/json";requestOptions.body=JSON.stringify(options.body);}
    try {
      const response=await fetch(`${getBaseUrl()}${endpoint}`,requestOptions); let payload={}; const contentType=response.headers.get("content-type")||""; if(contentType.includes("application/json")) payload=await response.json();
      if(!response.ok){if((response.status===401||response.status===403)&&options.redirectOnAuthFailure!==false){clearToken();redirectToLogin();} const message=typeof payload.detail==="string"?payload.detail:"The request could not be completed."; throw new ApiError(message,response.status,payload);} return payload;
    } catch(error) { if(error.name==="AbortError") throw new ApiError("The request timed out. Try again.",0,{}); throw error; }
    finally { window.clearTimeout(timeoutId); }
  }
  window.AuditApi=Object.freeze({request,ApiError,getToken,setToken,clearToken,redirectToLogin});
})();
