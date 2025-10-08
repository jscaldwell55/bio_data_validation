#!/bin/bash
# System test: Verify all system components are properly installed and configured
# Usage: ./test_components.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counter
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

run_test() {
    ((TESTS_RUN++))
    print_test "$1"
    
    if eval "$2" > /dev/null 2>&1; then
        print_pass "$1"
        return 0
    else
        print_fail "$1"
        return 1
    fi
}

# Start tests
print_header "System Component Verification Tests"
echo ""

# ===== PYTHON ENVIRONMENT =====
print_header "Python Environment"
echo ""

run_test "Python 3.11+ installed" "python3 --version | grep -E 'Python 3\.(11|12)'"
run_test "Poetry installed" "poetry --version"
run_test "Virtual environment exists" "test -d .venv || poetry env info"

echo ""

# ===== PROJECT STRUCTURE =====
print_header "Project Structure"
echo ""

run_test "Source directory exists" "test -d src"
run_test "Tests directory exists" "test -d tests"
run_test "Config directory exists" "test -d config"
run_test "Data directory exists" "test -d data"
run_test "pyproject.toml exists" "test -f pyproject.toml"
run_test "poetry.lock exists" "test -f poetry.lock"
run_test "README.md exists" "test -f README.md"

echo ""

# ===== PYTHON DEPENDENCIES =====
print_header "Python Dependencies"
echo ""

run_test "pandas installed" "poetry run python -c 'import pandas'"
run_test "pydantic installed" "poetry run python -c 'import pydantic'"
run_test "fastapi installed" "poetry run python -c 'import fastapi'"
run_test "pytest installed" "poetry run python -c 'import pytest'"
run_test "biopython installed" "poetry run python -c 'import Bio'"
run_test "aiohttp installed" "poetry run python -c 'import aiohttp'"

echo ""

# ===== SOURCE MODULES =====
print_header "Source Modules"
echo ""

run_test "Validators module exists" "test -d src/validators"
run_test "Agents module exists" "test -d src/agents"
run_test "Engine module exists" "test -d src/engine"
run_test "Schemas module exists" "test -d src/schemas"
run_test "API module exists" "test -d src/api"
run_test "Utils module exists" "test -d src/utils"

echo ""

# ===== CONFIGURATION FILES =====
print_header "Configuration Files"
echo ""

run_test "Validation rules config exists" "test -f config/validation_rules.yml"
run_test "Policy config exists" "test -f config/policy_config.yml"
run_test "Pytest config exists" "test -f pytest.ini"
run_test ".gitignore exists" "test -f .gitignore"

echo ""

# ===== TEST STRUCTURE =====
print_header "Test Structure"
echo ""

run_test "Unit tests directory exists" "test -d tests/unit"
run_test "Integration tests directory exists" "test -d tests/integration"
run_test "E2E tests directory exists" "test -d tests/e2e"
run_test "System tests directory exists" "test -d tests/system"
run_test "conftest.py exists" "test -f tests/conftest.py"

echo ""

# ===== EXAMPLE DATA =====
print_header "Example Data"
echo ""

run_test "Examples directory exists" "test -d data/examples"
run_test "Valid example data exists" "test -f data/examples/example_guide_rnas.csv"
run_test "Invalid example data exists" "test -f data/examples/example_invalid_guide_rnas.csv"

echo ""

# ===== PYTHON SYNTAX =====
print_header "Python Syntax Validation"
echo ""

if command -v python3 &> /dev/null; then
    print_test "Checking Python syntax in src/"
    if poetry run python -m py_compile src/**/*.py 2>/dev/null; then
        print_pass "All Python files in src/ have valid syntax"
    else
        print_fail "Some Python files have syntax errors"
    fi
    ((TESTS_RUN++))
fi

echo ""

# ===== IMPORT VALIDATION =====
print_header "Module Import Validation"
echo ""

run_test "Can import base schemas" "poetry run python -c 'from src.schemas.base_schemas import ValidationResult'"
run_test "Can import orchestrator" "poetry run python -c 'from src.agents.orchestrator import ValidationOrchestrator'"
run_test "Can import validators" "poetry run python -c 'from src.validators.schema_validator import SchemaValidator'"

echo ""

# ===== PYTEST SETUP =====
print_header "Pytest Setup"
echo ""

run_test "Pytest can discover tests" "poetry run pytest --collect-only tests/ | grep -q 'test session starts'"
run_test "Pytest markers configured" "poetry run pytest --markers | grep -q 'integration'"
run_test "Pytest coverage plugin available" "poetry run pytest --version | grep -q coverage || poetry run python -c 'import pytest_cov'"

echo ""

# ===== OPTIONAL COMPONENTS =====
print_header "Optional Components"
echo ""

if command -v docker &> /dev/null; then
    print_pass "Docker installed"
    ((TESTS_RUN++))
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}[SKIP]${NC} Docker not installed (optional)"
fi

if test -f Dockerfile; then
    print_pass "Dockerfile exists"
    ((TESTS_RUN++))
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}[SKIP]${NC} Dockerfile not found (optional)"
fi

if test -f docker-compose.yml; then
    print_pass "docker-compose.yml exists"
    ((TESTS_RUN++))
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}[SKIP]${NC} docker-compose.yml not found (optional)"
fi

echo ""

# ===== FINAL SUMMARY =====
print_header "Test Summary"
echo ""

echo -e "Tests Run:    ${BLUE}$TESTS_RUN${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All system components verified successfully!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some system components failed verification${NC}"
    echo -e "${YELLOW}Please fix the failed components before proceeding${NC}"
    exit 1
fi