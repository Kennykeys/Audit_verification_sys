from pathlib import Path

def read(path): return Path(path).read_text(encoding="utf-8")

def test_integrity_page_has_accessible_graph_and_text_alternative():
    page=read("frontend/integrity.html")
    assert 'id="integrityGraph"' in page and 'id="integrityTextGraph"' in page
    assert 'aria-live="polite"' in page and 'tabindex="0"' in page
    assert page.index("js/api.js") < page.index("js/integrity-graph.js")

def test_graph_renderer_uses_real_api_and_safe_dom_nodes():
    source=read("frontend/js/integrity-graph.js")
    assert 'AuditApi.request("/integrity/graph")' in source
    assert "createElement" in source and "textContent" in source and "innerHTML" not in source

def test_graph_renderer_exposes_required_states():
    source=read("frontend/js/integrity-graph.js").lower()
    for state in ("loading integrity graph","empty","valid","invalid","unchecked","unavailable"): assert state in source
    assert "first_invalid_sequence" in source and "failure_type" in source

def test_graph_styles_support_horizontal_navigation_and_non_color_signals():
    styles=read("frontend/style.css")
    assert ".integrity-graph" in styles and "overflow-x: auto" in styles
    assert ".chain-node--invalid" in styles and ".chain-link--invalid" in styles
    assert "⚠" in read("frontend/js/integrity-graph.js")

def test_dashboard_links_to_integrity_view_and_verification_is_structured():
    page=read("frontend/index.html"); app=read("frontend/app.js")
    assert 'href="integrity.html"' in page
    assert "createElement" in app and "innerHTML" not in app
    assert "record_valid" in app and "ledger_context_valid" in app
