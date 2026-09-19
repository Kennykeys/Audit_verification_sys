# Comprehensive Project Quality Gate

## Command

Run the complete deterministic gate from the repository root:

```sh
scripts/validate.sh
```

The script reports the real exit status of every command and exits nonzero if any step fails.

## Included controls

The gate runs repository-boundary tests, critical Python lint checks, formatting validation for Phase 11-owned Python, JavaScript syntax checks for every frontend script, full Pytest regression tests, and backend branch coverage.

## Coverage threshold

The initial backend coverage threshold is **70%** with branch coverage enabled. This threshold is intentionally above a simple majority while remaining achievable for the existing mix of API modules, migration paths, operational scripts, and filesystem failure branches. The threshold must only move upward in later phases.

The empty `backend/services/__init__.py` package marker is omitted. Standard defensive-only lines may be excluded only through the explicit patterns in `pyproject.toml`. No authentication, integrity, persistence, or security-control branch is excluded.

## Linting and formatting policy

Ruff checks all backend and test Python files for syntax-level and undefined-name failures using `E9`, `F63`, `F7`, and `F82`. Full-repository auto-formatting is not introduced retroactively because production files are outside this phase's formatting scope. Ruff formatting is enforced for the new repository-boundary test.

## Repository boundaries

The gate rejects accepted hard-coded administrator credentials, wildcard CORS, unsafe transaction or graph `innerHTML`, tracked generated artifacts, quality-gate security bypass tokens, and mutation tests that do not declare temporary-ledger boundaries.

## Determinism

Phase completion requires two consecutive successful runs from the same commit and environment. Transient artifacts such as `.coverage`, `coverage.xml`, caches, and test results are ignored by Git and must not be committed.

## Test safety

Mutating tests use temporary ledgers. Authentication tests use generated mock credentials and bcrypt verifiers. The validation script does not disable authentication, integrity, persistence, or security controls.
