#!/bin/bash
# ============================================
# Integration Test Runner for V0Agent
# ============================================
# Runs integration tests (API endpoints, DB)
# Usage: ./test_integration.sh [pytest options]
# ============================================

set -e

# Ensure we're in the project root
cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "============================================"
echo "  INTEGRATION TESTS"
echo "============================================"
echo ""

# Run integration folder tests
pytest tests/integration/ -v --tb=short "$@"

echo ""
echo "============================================"
echo "  API TESTS"
echo "============================================"
echo ""

# Run top-level API/feature tests
pytest tests/test_api_*.py tests/test_imports*.py tests/test_search*.py tests/test_unified*.py -v --tb=short "$@"
