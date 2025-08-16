#!/bin/bash

echo "🧪 Unspend Platform Test Suite"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test and track results
run_test() {
    local test_name=$1
    local test_command=$2
    
    echo -e "${YELLOW}Running: $test_name${NC}"
    if eval "$test_command"; then
        echo -e "${GREEN}✅ $test_name passed${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ $test_name failed${NC}"
        ((TESTS_FAILED++))
    fi
    echo ""
}

# Create necessary directories
mkdir -p test_reports
mkdir -p coverage_reports

# Python Backend Tests
echo "📦 Setting up Python environment..."
pip install -q pytest pytest-cov pytest-asyncio black flake8 safety bandit

echo ""
echo "🔍 Running Backend Tests"
echo "------------------------"

# Linting
run_test "Python Linting (flake8)" "flake8 backend/ --count --select=E9,F63,F7,F82 --show-source --statistics"

# Code formatting check
run_test "Python Formatting (black)" "black --check backend/ 2>/dev/null"

# Security checks
run_test "Security Scan (bandit)" "bandit -r backend/ -f json -o test_reports/bandit.json 2>/dev/null"
run_test "Dependency Security (safety)" "safety check --json > test_reports/safety.json 2>/dev/null"

# Unit tests
run_test "Backend Unit Tests" "pytest backend/tests/ -v --cov=backend --cov-report=html:coverage_reports/backend"

# Integration test
echo ""
echo "🔗 Running Integration Tests"
echo "----------------------------"

# Start backend server in background for integration tests
echo "Starting backend server..."
cd backend && python app.py &
BACKEND_PID=$!
sleep 5

# Test API endpoints
run_test "API Health Check" "curl -s http://localhost:5000/api/health | grep -q 'healthy'"

# Kill backend server
kill $BACKEND_PID 2>/dev/null
cd ..

# Frontend Tests
echo ""
echo "🎨 Running Frontend Tests"
echo "------------------------"

# HTML validation
if command -v html-validate &> /dev/null; then
    run_test "HTML Validation" "html-validate frontend/*.html"
else
    echo "⚠️  html-validate not installed, skipping HTML validation"
fi

# JavaScript linting
if command -v eslint &> /dev/null; then
    run_test "JavaScript Linting" "eslint frontend/*.js --format json -o test_reports/eslint.json"
else
    echo "⚠️  eslint not installed, skipping JavaScript linting"
fi

# Firebase Configuration Tests
echo ""
echo "🔥 Testing Firebase Configuration"
echo "---------------------------------"

run_test "Firebase Config Valid" "test -f firebase.json && test -f .firebaserc"
run_test "Deploy Script Executable" "test -x deploy.sh"

# Performance Tests
echo ""
echo "⚡ Running Performance Tests"
echo "---------------------------"

# Check file sizes
run_test "Frontend Bundle Size" "[ $(find frontend -name '*.js' -exec du -k {} + | awk '{s+=$1} END {print s}') -lt 1000 ]"

# Test Results Summary
echo ""
echo "📊 Test Results Summary"
echo "======================"
echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Tests Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! Ready for deployment.${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Some tests failed. Please fix issues before deployment.${NC}"
    exit 1
fi