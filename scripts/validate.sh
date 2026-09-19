#!/bin/sh
set -u

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$ROOT_DIR/.venv/bin/python"
RUFF="$ROOT_DIR/.venv/bin/ruff"
NODE_BIN=${NODE_BIN:-node}
FAILURES=0

run_step() {
    step_name=$1
    shift
    printf '%s
' "=== $step_name ==="
    "$@"
    step_status=$?
    if [ "$step_status" -eq 0 ]; then
        printf '%s
' "$step_name: PASS"
    else
        printf '%s
' "$step_name: FAIL status=$step_status"
        FAILURES=$((FAILURES + 1))
    fi
}

if [ ! -x "$PYTHON" ]; then
    printf '%s
' "Python virtual environment missing: $PYTHON"
    exit 1
fi

if [ ! -x "$RUFF" ]; then
    printf '%s
' "Ruff missing: install requirements-dev.txt"
    exit 1
fi

cd "$ROOT_DIR"

run_step "Repository boundary tests" "$PYTHON" -m pytest -q tests/test_repository_boundaries.py
run_step "Python critical lint" "$RUFF" check backend tests
run_step "Phase 11 Python format" "$RUFF" format --check tests/test_repository_boundaries.py

for javascript_file in $(find frontend -type f -name '*.js' | sort); do
    run_step "JavaScript syntax $javascript_file" "$NODE_BIN" --check "$javascript_file"
done

run_step "Backend coverage and full regression" "$PYTHON" -m pytest -q --cov=backend --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=70

if [ "$FAILURES" -eq 0 ]; then
    printf '%s
' 'AUDIT_VERIFICATION_COMPREHENSIVE_QUALITY_GATE_COMPLETE'
    exit 0
fi

printf '%s
' "AUDIT_VERIFICATION_COMPREHENSIVE_QUALITY_GATE_BLOCKED failures=$FAILURES"
exit 1
