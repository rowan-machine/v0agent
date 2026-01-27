#!/bin/bash
# ============================================
# Unit Test Runner for V0Agent
# ============================================
# Runs only unit tests (fast, no external deps)
# Usage: ./test_unit.sh [pytest options]
# ============================================

set -e

# Ensure we're in the project root
cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "============================================"
echo "  UNIT TESTS"
echo "============================================"
echo ""

pytest tests/unit/ -v --tb=short "$@"
