from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_configured_origin_allowed_and_unknown_origin_denied():
    allowed = client.options("/integrity", headers={"Origin":"http://127.0.0.1:8000","Access-Control-Request-Method":"GET"})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:8000"
    denied = client.options("/integrity", headers={"Origin":"https://not-configured.example","Access-Control-Request-Method":"GET"})
    assert denied.status_code == 400
    assert denied.headers.get("access-control-allow-origin") is None

def test_invalid_host_rejected():
    assert client.get("/integrity", headers={"Host":"not-configured.example"}).status_code == 400

def test_security_headers_and_request_id_on_success_and_failure():
    for response in (client.get("/integrity"), client.get("/auth/me")):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["content-security-policy"]
        assert response.headers["permissions-policy"]
        assert response.headers["x-request-id"]

def test_oversized_request_rejected():
    response = client.post("/auth/login", content=b"x" * 65537, headers={"Content-Type":"application/json"})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"

def test_login_rate_limit():
    statuses = [client.post("/auth/login", json={"username":"missing","password":"invalid"}).status_code for _ in range(6)]
    assert statuses[-1] == 429
    assert "retry-after" in client.post("/auth/login", json={"username":"missing","password":"invalid"}).headers

def test_validation_error_is_normalized_without_traceback():
    response = client.post("/record", json={})
    assert response.status_code in {401, 422}
    assert "traceback" not in response.text.lower()
