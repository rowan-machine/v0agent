#!/bin/bash
# ============================================
# Compile/Syntax Test for V0Agent
# ============================================
# Quick check that Python files compile
# Usage: ./test_compile.sh
# ============================================

set -e

# Ensure we're in the project root
cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "============================================"
echo "  COMPILE TESTS"
echo "============================================"
echo ""

# Check key Python files compile
echo "Checking Python syntax..."
python -m py_compile src/app/main.py
python -m py_compile src/app/meetings.py
python -m py_compile src/app/config.py

# Check API modules
for f in src/app/api/*.py; do
    if [ -f "$f" ]; then
        python -m py_compile "$f"
    fi
done

# Check services
for f in src/app/services/*.py; do
    if [ -f "$f" ]; then
        python -m py_compile "$f"
    fi
done

# Check core modules
for f in src/app/core/*.py; do
    if [ -f "$f" ]; then
        python -m py_compile "$f"
    fi
done

echo "✓ All Python files compile successfully"
echo ""

# Check imports work
echo "Checking imports..."
python -c "
from src.app.main import app
from src.app.infrastructure.supabase_client import get_supabase_client
print('✓ All critical imports successful')
"
echo ""
echo "============================================"
echo "  COMPILE TESTS PASSED"
echo "============================================"
