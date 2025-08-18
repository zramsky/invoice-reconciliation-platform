#!/bin/bash

echo "🧪 Production Testing Suite"
echo "=========================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_code="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    print_status "Testing: $test_name"
    
    # Run the test command and capture both output and HTTP code
    response=$(eval "$test_command")
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        print_success "$test_name"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        print_error "$test_name - Exit code: $exit_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Configuration
BACKEND_URL="${BACKEND_URL:-https://invoice-reconciliation-backend.fly.dev}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:8080}"

echo "Backend URL: $BACKEND_URL"
echo "Frontend URL: $FRONTEND_URL"
echo ""

# Backend API Tests
echo "🔧 BACKEND API TESTS"
echo "==================="

run_test "Ping endpoint" \
    "curl -s -f $BACKEND_URL/api/ping > /dev/null"

run_test "Health endpoint" \
    "curl -s -f $BACKEND_URL/api/health > /dev/null"

run_test "Vendors list endpoint" \
    "curl -s -f $BACKEND_URL/api/vendors > /dev/null"

run_test "Monitoring health endpoint" \
    "curl -s -f $BACKEND_URL/api/monitor/health > /dev/null"

run_test "Monitoring performance endpoint" \
    "curl -s -f $BACKEND_URL/api/monitor/performance > /dev/null"

# Test response times
echo ""
echo "⏱️  PERFORMANCE TESTS"
echo "==================="

print_status "Testing response times..."

# Test ping response time
ping_time=$(curl -o /dev/null -s -w "%{time_total}" $BACKEND_URL/api/ping)
ping_ms=$(echo "$ping_time * 1000" | bc)

if (( $(echo "$ping_time < 5.0" | bc -l) )); then
    print_success "Ping response time: ${ping_ms}ms (< 5000ms)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    print_error "Ping response time: ${ping_ms}ms (>= 5000ms)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test vendors API response time
vendors_time=$(curl -o /dev/null -s -w "%{time_total}" $BACKEND_URL/api/vendors)
vendors_ms=$(echo "$vendors_time * 1000" | bc)

if (( $(echo "$vendors_time < 10.0" | bc -l) )); then
    print_success "Vendors API response time: ${vendors_ms}ms (< 10000ms)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    print_error "Vendors API response time: ${vendors_ms}ms (>= 10000ms)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Database tests
echo ""
echo "💾 DATABASE TESTS"
echo "================"

# Test creating a vendor
print_status "Testing vendor creation..."

# Create test vendor
test_vendor_data=$(cat << 'EOF'
{
    "vendor_name": "Test Automation Vendor",
    "business_description": "Automated testing vendor",
    "effective_date": "2025-08-18",
    "renewal_date": "2026-08-18",
    "reconciliation_summary": "Automated test contract"
}
EOF
)

create_response=$(curl -s -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$test_vendor_data" \
    $BACKEND_URL/api/vendors)

create_code="${create_response: -3}"
create_body="${create_response%???}"

if [ "$create_code" = "201" ]; then
    print_success "Vendor creation test"
    PASSED_TESTS=$((PASSED_TESTS + 1))
    
    # Extract vendor ID from response
    vendor_id=$(echo "$create_body" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$vendor_id" ]; then
        print_status "Created vendor ID: $vendor_id"
        
        # Test getting the vendor
        get_response=$(curl -s -w "%{http_code}" $BACKEND_URL/api/vendors/$vendor_id)
        get_code="${get_response: -3}"
        
        if [ "$get_code" = "200" ]; then
            print_success "Vendor retrieval test"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            print_error "Vendor retrieval test - HTTP $get_code"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
        TOTAL_TESTS=$((TOTAL_TESTS + 1))
    fi
else
    print_error "Vendor creation test - HTTP $create_code"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Frontend tests (if accessible)
echo ""
echo "🌐 FRONTEND TESTS"
echo "================"

if curl -s -f $FRONTEND_URL > /dev/null 2>&1; then
    run_test "Frontend accessibility" \
        "curl -s -f $FRONTEND_URL > /dev/null"
    
    run_test "Frontend main page loads" \
        "curl -s $FRONTEND_URL | grep -q 'Invoice Reconciliation'"
    
    run_test "Frontend config.js loads" \
        "curl -s -f $FRONTEND_URL/frontend/config.js > /dev/null"
else
    print_warning "Frontend not accessible at $FRONTEND_URL - skipping frontend tests"
fi

# Security tests
echo ""
echo "🔒 SECURITY TESTS"
echo "================"

run_test "CORS headers present" \
    "curl -s -I $BACKEND_URL/api/ping | grep -q 'Access-Control-Allow'"

run_test "Security headers present" \
    "curl -s -I $BACKEND_URL/api/ping | grep -q 'X-Content-Type-Options\\|X-Frame-Options'"

# Load testing (basic)
echo ""
echo "📊 LOAD TESTS"
echo "============="

print_status "Running basic load test (10 concurrent requests)..."

# Create temporary file for results
temp_file=$(mktemp)

# Run 10 concurrent requests
for i in {1..10}; do
    (
        time_taken=$(curl -o /dev/null -s -w "%{time_total}" $BACKEND_URL/api/ping)
        echo "$time_taken" >> "$temp_file"
    ) &
done

# Wait for all background jobs to complete
wait

# Calculate statistics
if [ -f "$temp_file" ]; then
    avg_time=$(awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}' "$temp_file")
    max_time=$(awk 'BEGIN{max=0} {if($1>max) max=$1} END{print max}' "$temp_file")
    
    avg_ms=$(echo "$avg_time * 1000" | bc)
    max_ms=$(echo "$max_time * 1000" | bc)
    
    print_status "Load test results:"
    echo "  Average response time: ${avg_ms}ms"
    echo "  Maximum response time: ${max_ms}ms"
    
    if (( $(echo "$avg_time < 5.0" | bc -l) )); then
        print_success "Load test performance acceptable"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_error "Load test performance poor (avg > 5000ms)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    
    rm -f "$temp_file"
else
    print_error "Load test failed to complete"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Final report
echo ""
echo "📋 TEST SUMMARY"
echo "=============="
echo "Total tests: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"

if [ $FAILED_TESTS -eq 0 ]; then
    print_success "🎉 ALL TESTS PASSED!"
    echo ""
    echo "✅ Your platform is production-ready!"
    echo "✅ API endpoints are working"
    echo "✅ Database operations successful"
    echo "✅ Performance is acceptable"
    echo "✅ Basic security measures in place"
    exit 0
else
    print_error "❌ Some tests failed!"
    echo ""
    echo "Please review the failed tests above and fix issues before production deployment."
    exit 1
fi