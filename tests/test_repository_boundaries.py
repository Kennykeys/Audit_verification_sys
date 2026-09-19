from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def source_files(base, suffixes):
    return sorted(
        path
        for path in (ROOT / base).rglob("*")
        if path.is_file() and path.suffix in suffixes and "__pycache__" not in path.parts
    )


def combined_text(paths):
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


@pytest.mark.boundary
def test_no_hard_coded_accepted_administrator_credentials():
    text = combined_text(source_files("backend", {".py"}) + source_files("frontend", {".js", ".html"}))
    normalized = re.sub(r"\s+", "", text).lower()
    forbidden = (
        'req.member_id=="admin"',
        "req.member_id=='admin'",
        'req.password=="admin"',
        "req.password=='admin'",
    )
    assert all(candidate not in normalized for candidate in forbidden)


@pytest.mark.boundary
def test_no_wildcard_cors_configuration():
    text = combined_text(source_files("backend", {".py"}))
    normalized = re.sub(r"\s+", "", text)
    assert 'allow_origins=["*"]' not in normalized
    assert "allow_origins=['*']" not in normalized


@pytest.mark.boundary
def test_transaction_and_integrity_renderers_do_not_use_inner_html():
    paths = [
        ROOT / "frontend/app.js",
        ROOT / "frontend/transactions.js",
        ROOT / "frontend/js/integrity-graph.js",
    ]
    for path in paths:
        assert "innerHTML" not in path.read_text(encoding="utf-8")


@pytest.mark.boundary
def test_generated_files_are_not_tracked():
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    forbidden_parts = {"__pycache__", ".pytest_cache", ".ruff_cache", "htmlcov", "node_modules", "dist", "build"}
    forbidden_names = {".coverage", "coverage.xml", "junit.xml"}
    violations = []
    for relative in tracked:
        path = Path(relative)
        if forbidden_parts.intersection(path.parts) or path.name in forbidden_names or path.suffix in {".pyc", ".pyo"}:
            violations.append(relative)
    assert violations == []


@pytest.mark.boundary
def test_quality_gate_does_not_disable_security_controls():
    script = (ROOT / "scripts/validate.sh").read_text(encoding="utf-8")
    forbidden = ("SKIP_AUTH", "DISABLE_AUTH", "SKIP_INTEGRITY", "DISABLE_INTEGRITY", "SKIP_PERSISTENCE")
    assert all(token not in script for token in forbidden)


@pytest.mark.boundary
def test_mutating_tests_use_temporary_ledger_boundaries():
    relevant = [
        ROOT / "tests/api/test_recording_workflow.py",
        ROOT / "tests/backend/test_repository.py",
        ROOT / "tests/backend/test_concurrency.py",
        ROOT / "tests/backend/test_transaction_api_integrity.py",
    ]
    for path in relevant:
        text = path.read_text(encoding="utf-8")
        assert "tmp_path" in text
