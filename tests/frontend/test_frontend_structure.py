from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
HTML_FILES = (
    FRONTEND_ROOT / "index.html",
    FRONTEND_ROOT / "login.html",
    FRONTEND_ROOT / "member_login.html",
    FRONTEND_ROOT / "transactions.html",
)
SCRIPT_FILES = (
    FRONTEND_ROOT / "app.js",
    FRONTEND_ROOT / "index.js",
    FRONTEND_ROOT / "login.js",
    FRONTEND_ROOT / "member_login.js",
    FRONTEND_ROOT / "transactions.js",
    FRONTEND_ROOT / "js" / "config.js",
    FRONTEND_ROOT / "js" / "ui.js",
)


class DocumentInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.labels = set()
        self.scripts = []
        self.skip_links = 0
        self.live_regions = 0
        self.scoped_headers = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)
        if tag == "label" and attributes.get("for"):
            self.labels.add(attributes["for"])
        if tag == "script" and attributes.get("src"):
            self.scripts.append(attributes["src"])
        if tag == "a" and attributes.get("class") == "skip-link":
            if attributes.get("href") == "#main-content":
                self.skip_links += 1
        if attributes.get("aria-live"):
            self.live_regions += 1
        if tag == "th" and attributes.get("scope") == "col":
            self.scoped_headers += 1


def inspect_document(file_path):
    inspector = DocumentInspector()
    inspector.feed(file_path.read_text(encoding="utf-8"))
    inspector.close()
    return inspector


def test_required_frontend_files_exist():
    required_files = HTML_FILES + SCRIPT_FILES + (
        FRONTEND_ROOT / "style.css",
        FRONTEND_ROOT / "assets" / ".gitkeep",
    )
    missing = [str(file_path) for file_path in required_files if not file_path.exists()]
    assert not missing, f"Missing frontend files: {missing}"


def test_pages_have_accessible_landmarks_and_live_regions():
    for file_path in HTML_FILES:
        inspector = inspect_document(file_path)
        assert inspector.skip_links == 1, file_path
        assert "main-content" in inspector.ids, file_path
        assert inspector.live_regions >= 1, file_path


def test_form_controls_have_programmatic_labels():
    expected_labels = {
        "index.html": {"verify_id", "network", "phoneNumber", "mmAmount", "mmMemberId", "mmDescription"},
        "login.html": {"username", "password"},
        "member_login.html": {"memberId", "password"},
        "transactions.html": {"transactionId", "amount", "memberId", "description"},
    }
    for filename, field_ids in expected_labels.items():
        inspector = inspect_document(FRONTEND_ROOT / filename)
        assert field_ids.issubset(inspector.labels), filename


def test_shared_scripts_load_before_page_script():
    primary_scripts = {
        "index.html": "index.js",
        "login.html": "login.js",
        "member_login.html": "member_login.js",
        "transactions.html": "transactions.js",
    }
    for filename, primary_script in primary_scripts.items():
        scripts = inspect_document(FRONTEND_ROOT / filename).scripts
        assert scripts.count("js/config.js") == 1, filename
        assert scripts.count("js/ui.js") == 1, filename
        assert scripts.count(primary_script) == 1, filename
        assert scripts.index("js/config.js") < scripts.index("js/ui.js") < scripts.index(primary_script), filename


def test_transactions_table_has_scoped_headers():
    inspector = inspect_document(FRONTEND_ROOT / "transactions.html")
    assert inspector.scoped_headers == 9


def test_frontend_references_are_centralized_and_safe():
    frontend_sources = [file_path.read_text(encoding="utf-8") for file_path in HTML_FILES + SCRIPT_FILES + (FRONTEND_ROOT / "style.css",)]
    combined = "\n".join(frontend_sources)
    non_config_sources = [file_path.read_text(encoding="utf-8") for file_path in HTML_FILES + tuple(file_path for file_path in SCRIPT_FILES if file_path.name != "config.js") + (FRONTEND_ROOT / "style.css",)]
    assert "background.jpg" not in combined
    assert "http://127.0.0.1:8000" not in "\n".join(non_config_sources)
    assert "innerHTML" not in combined


def test_design_system_contains_responsive_and_accessible_rules():
    stylesheet = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")
    required_rules = (
        ":root",
        "min-width: 320px",
        "min-height: 48px",
        "overflow-x: auto",
        "prefers-reduced-motion: reduce",
        "prefers-contrast: more",
        ".skip-link",
        ".table-container",
        ".status-panel",
    )
    for required_rule in required_rules:
        assert required_rule in stylesheet


def test_dashboard_uses_integrity_verification_api():
    dashboard_script = (FRONTEND_ROOT / "index.js").read_text(encoding="utf-8")
    dashboard_page = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    configuration = (FRONTEND_ROOT / "js" / "config.js").read_text(encoding="utf-8")
    assert "/verify/${encodeURIComponent(transactionId)}" in dashboard_script
    assert "Verifying transaction integrity..." in dashboard_script
    assert "passed integrity verification" in dashboard_script
    assert "failed integrity verification" in dashboard_script
    assert "Integrity verification available" in dashboard_page
    assert "Deterministic SHA-256 verification available" in configuration
    assert "Integrity status unavailable" not in dashboard_page
