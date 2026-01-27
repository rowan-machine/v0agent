#!/bin/bash
# ============================================
# Master Test Runner for V0Agent
# ============================================
# Run all tests with comprehensive reporting
# Usage: ./test_all.sh [options]
#   --quick     Run only compile + unit tests
#   --smoke     Run smoke tests only
#   --verbose   Show detailed output
#   --coverage  Generate coverage report
# ============================================

set -e  # Exit on first error

# Ensure we're in the project root
cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track results
TOTAL_PASSED=0
TOTAL_FAILED=0
FAILED_SUITES=()

# Parse arguments
QUICK_MODE=false
SMOKE_ONLY=false
VERBOSE=false
COVERAGE=false

for arg in "$@"; do
    case $arg in
        --quick)
            QUICK_MODE=true
            ;;
        --smoke)
            SMOKE_ONLY=true
            ;;
        --verbose)
            VERBOSE=true
            ;;
        --coverage)
            COVERAGE=true
            ;;
        --help)
            echo "Usage: ./test_all.sh [options]"
            echo "  --quick     Run only compile + unit tests"
            echo "  --smoke     Run smoke tests only"
            echo "  --verbose   Show detailed output"
            echo "  --coverage  Generate coverage report"
            exit 0
            ;;
    esac
done

# Print header
print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================${NC}"
}

# Print result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2 PASSED${NC}"
        ((TOTAL_PASSED++))
    else
        echo -e "${RED}✗ $2 FAILED${NC}"
        ((TOTAL_FAILED++))
        FAILED_SUITES+=("$2")
    fi
}

# Run a test suite
run_suite() {
    local name=$1
    local command=$2
    
    echo ""
    echo -e "${YELLOW}Running: $name${NC}"
    echo "Command: $command"
    echo "---"
    
    if $VERBOSE; then
        if eval $command; then
            print_result 0 "$name"
        else
            print_result 1 "$name"
        fi
    else
        if eval $command > /tmp/test_output_$$.txt 2>&1; then
            print_result 0 "$name"
        else
            print_result 1 "$name"
            echo "Output:"
            tail -50 /tmp/test_output_$$.txt
        fi
        rm -f /tmp/test_output_$$.txt
    fi
}

# ============================================
# COMPILE TESTS
# ============================================
print_header "COMPILE TESTS"
echo "Checking Python syntax and imports..."

run_suite "Python Syntax Check" "python -m py_compile src/app/main.py"
run_suite "Import Verification" "python -c 'from src.app.main import app; print(\"FastAPI app loaded successfully\")'"

# ============================================
# UNIT TESTS
# ============================================
print_header "UNIT TESTS"

PYTEST_OPTS="-v --tb=short"
if $COVERAGE; then
    PYTEST_OPTS="$PYTEST_OPTS --cov=src --cov-report=term-missing"
fi

run_suite "Domain Models" "pytest tests/unit/test_domain_models.py $PYTEST_OPTS"
run_suite "SDK Client" "pytest tests/unit/test_sdk_client.py $PYTEST_OPTS"

if $QUICK_MODE; then
    echo ""
    echo -e "${YELLOW}Quick mode: Skipping integration and e2e tests${NC}"
else
    # ============================================
    # INTEGRATION TESTS
    # ============================================
    print_header "INTEGRATION TESTS"
    
    run_suite "DIKW API" "pytest tests/integration/test_api_dikw.py $PYTEST_OPTS"
    run_suite "AI Memory API" "pytest tests/test_api_ai_memory.py $PYTEST_OPTS"
    run_suite "Feedback API" "pytest tests/test_api_feedback.py $PYTEST_OPTS"
    run_suite "Meetings API" "pytest tests/test_api_meetings.py $PYTEST_OPTS"
    run_suite "Background Jobs" "pytest tests/test_background_jobs.py $PYTEST_OPTS"
    run_suite "Coach Recommendations" "pytest tests/test_coach_recommendations.py $PYTEST_OPTS"
    run_suite "Notifications API" "pytest tests/test_notifications_api.py $PYTEST_OPTS"
    run_suite "Notifications UI" "pytest tests/test_notifications_ui.py $PYTEST_OPTS"
    run_suite "UI Settings" "pytest tests/test_ui_settings.py $PYTEST_OPTS"
    run_suite "Shortcuts" "pytest tests/test_shortcuts.py $PYTEST_OPTS"
    run_suite "Signal Learning" "pytest tests/test_signal_learning.py $PYTEST_OPTS"
    run_suite "Supabase Sync" "pytest tests/test_supabase_sync.py $PYTEST_OPTS"
    
    # ============================================
    # IMPORT TESTS (Feature-specific)
    # ============================================
    print_header "IMPORT TESTS"
    
    run_suite "Basic Imports (F1a)" "pytest tests/test_imports.py $PYTEST_OPTS"
    run_suite "Amend Imports (F1b)" "pytest tests/test_imports_amend.py $PYTEST_OPTS"
    run_suite "Mindmap Imports (F1c)" "pytest tests/test_imports_mindmap.py $PYTEST_OPTS"
    
    # ============================================
    # SEARCH TESTS
    # ============================================
    print_header "SEARCH TESTS"
    
    run_suite "Full-Text Search (F2)" "pytest tests/test_search_fulltext.py $PYTEST_OPTS"
    run_suite "Unified Search (F5)" "pytest tests/test_unified_search.py $PYTEST_OPTS"
    
    # ============================================
    # AI/COACHING TESTS
    # ============================================
    print_header "AI & COACHING TESTS"
    
    run_suite "Quick AI Updates" "pytest tests/test_quick_ai_my_updates.py $PYTEST_OPTS"
    
    # ============================================
    # CUTOVER VERIFICATION
    # ============================================
    if ! $SMOKE_ONLY; then
        print_header "CUTOVER VERIFICATION"
        run_suite "Cutover Tests" "pytest tests/test_cutover_verification.py $PYTEST_OPTS"
    fi
fi

# ============================================
# SUMMARY
# ============================================
print_header "TEST SUMMARY"

echo ""
echo -e "Total Suites Run: $((TOTAL_PASSED + TOTAL_FAILED))"
echo -e "${GREEN}Passed: $TOTAL_PASSED${NC}"
echo -e "${RED}Failed: $TOTAL_FAILED${NC}"

if [ ${#FAILED_SUITES[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Failed Suites:${NC}"
    for suite in "${FAILED_SUITES[@]}"; do
        echo -e "  - $suite"
    done
    echo ""
    exit 1
else
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  ALL TESTS PASSED! 🎉${NC}"
    echo -e "${GREEN}============================================${NC}"
    exit 0
fi
