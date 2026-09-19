from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def test_api_client_centralizes_fetch_timeout_json_and_non_success_handling():
    api = read("frontend/js/api.js")
    assert "fetch(" in api
    assert "AbortController" in api
    assert "response.json()" in api
    assert "response.ok" in api
    assert "ApiError" in api


def test_recording_scripts_use_truthful_busy_validation_and_error_states():
    dashboard = read("frontend/app.js")
    transactions = read("frontend/transactions.js")
    assert "setBusy" in dashboard and "finally" in dashboard
    assert "setBusy" in transactions and "finally" in transactions
    assert "payload.detail" in dashboard
    assert "payload.detail" in transactions
    assert "success" in dashboard and "error" in dashboard
    assert "success" in transactions and "error" in transactions


def test_transaction_values_use_safe_dom_rendering():
    transactions = read("frontend/transactions.js")
    helper = read("frontend/js/ui.js")
    assert "createElement" in transactions or "createElement" in helper
    assert "textContent" in transactions or "textContent" in helper
    assert "innerHTML" not in transactions


def test_pages_load_centralized_api_before_runtime_scripts():
    dashboard = read("frontend/index.html")
    transactions = read("frontend/transactions.html")
    assert dashboard.index("js/api.js") < dashboard.index("app.js")
    assert transactions.index("js/api.js") < transactions.index("transactions.js")
    assert dashboard.count("index.js") == 1
    assert dashboard.index("js/api.js") < dashboard.index("app.js")


def test_mobile_money_is_truthfully_labelled_as_simulation():
    dashboard = read("frontend/index.html")
    assert "Mobile-money simulation" in dashboard
    assert "No provider PIN or secret is collected" in dashboard


def test_real_summary_bindings_replace_demo_totals():
    config = read("frontend/js/config.js")
    dashboard = read("frontend/app.js")
    transactions = read("frontend/transactions.js")
    assert "demoSummary" not in config
    assert "recordingSummary" in dashboard
    assert "transactionSummary" in transactions
    assert "'/transactions'" in dashboard
    assert "'/transactions'" in transactions


def test_frontend_runtime_scripts_do_not_call_fetch_directly():
    assert "fetch(" not in read("frontend/app.js")
    assert "fetch(" not in read("frontend/transactions.js")
