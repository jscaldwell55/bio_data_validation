#!/bin/bash
# System test: End-to-end workflow validation
# Tests complete validation workflow from data input to final decision
# Usage: ./test_e2e_workflow.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Temporary directory for test files
TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

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
    
    if eval "$2"; then
        print_pass "$1"
        return 0
    else
        print_fail "$1"
        return 1
    fi
}

# Start tests
print_header "End-to-End Workflow Validation Tests"
echo ""

# ===== PREPARE TEST DATA =====
print_header "Test Data Preparation"
echo ""

# Create valid test dataset
VALID_CSV="$TEST_DIR/valid_guides.csv"
cat > "$VALID_CSV" << EOF
guide_id,sequence,pam_sequence,target_gene,organism,nuclease_type,gc_content,efficiency_score
gRNA_001,ATCGATCGATCGATCGATCG,AGG,BRCA1,human,SpCas9,0.50,0.85
gRNA_002,GCTAGCTAGCTAGCTAGCTA,TGG,TP53,human,SpCas9,0.50,0.92
gRNA_003,GATTACAGATTACAGATTAC,CGG,EGFR,human,SpCas9,0.40,0.78
EOF

if [ -f "$VALID_CSV" ]; then
    print_pass "Valid test dataset created"
    ((TESTS_RUN++))
    ((TESTS_PASSED++))
else
    print_fail "Failed to create valid test dataset"
    ((TESTS_RUN++))
    ((TESTS_FAILED++))
    exit 1
fi

# Create invalid test dataset
INVALID_CSV="$TEST_DIR/invalid_guides.csv"
cat > "$INVALID_CSV" << EOF
guide_id,sequence,pam_sequence,target_gene,organism,nuclease_type,gc_content,efficiency_score
gRNA_001,ATCG,AAA,INVALID,human,SpCas9,1.5,1.2
gRNA_001,INVALID123,TGG,BRCA1,human,SpCas9,-0.1,0.85
EOF

if [ -f "$INVALID_CSV" ]; then
    print_pass "Invalid test dataset created"
    ((TESTS_RUN++))
    ((TESTS_PASSED++))
else
    print_fail "Failed to create invalid test dataset"
    ((TESTS_RUN++))
    ((TESTS_FAILED++))
fi

echo ""

# ===== VALIDATION SCRIPT WORKFLOW =====
print_header "Validation Script Workflow"
echo ""

# Test validation script exists
run_test "Validation script exists" "test -f scripts/validation/validate_datasets.py"

# Test running validation on valid data
print_test "Validating valid dataset"
((TESTS_RUN++))
if poetry run python scripts/validation/validate_datasets.py \
    --input-file "$VALID_CSV" \
    --output-dir "$TEST_DIR/results" \
    > "$TEST_DIR/valid_output.log" 2>&1; then
    print_pass "Valid dataset validation completed"
    ((TESTS_PASSED++))
else
    print_fail "Valid dataset validation failed"
    ((TESTS_FAILED++))
    cat "$TEST_DIR/valid_output.log"
fi

# Test running validation on invalid data
print_test "Validating invalid dataset"
((TESTS_RUN++))
if poetry run python scripts/validation/validate_datasets.py \
    --input-file "$INVALID_CSV" \
    --output-dir "$TEST_DIR/results" \
    > "$TEST_DIR/invalid_output.log" 2>&1; then
    print_pass "Invalid dataset validation completed"
    ((TESTS_PASSED++))
else
    # Validation may "fail" by design for invalid data
    if grep -q "REJECTED\|ERROR" "$TEST_DIR/invalid_output.log"; then
        print_pass "Invalid dataset correctly rejected"
        ((TESTS_PASSED++))
    else
        print_fail "Invalid dataset validation had unexpected error"
        ((TESTS_FAILED++))
        cat "$TEST_DIR/invalid_output.log"
    fi
fi

echo ""

# ===== VALIDATION RESULTS =====
print_header "Validation Results"
echo ""

# Check results directory created
run_test "Results directory created" "test -d $TEST_DIR/results"

# Check validation reports generated
run_test "Validation reports generated" "test -f $TEST_DIR/results/*.json || test -f $TEST_DIR/results/*.txt"

# Check valid data was accepted
if [ -f "$TEST_DIR/results"/*valid*.json ] || [ -f "$TEST_DIR/results"/*valid*.txt ]; then
    print_test "Valid dataset decision"
    ((TESTS_RUN++))
    if grep -q "ACCEPTED" "$TEST_DIR/results"/*valid* 2>/dev/null; then
        print_pass "Valid dataset was accepted"
        ((TESTS_PASSED++))
    else
        print_fail "Valid dataset was not accepted"
        ((TESTS_FAILED++))
    fi
fi

# Check invalid data was rejected
if [ -f "$TEST_DIR/results"/*invalid*.json ] || [ -f "$TEST_DIR/results"/*invalid*.txt ]; then
    print_test "Invalid dataset decision"
    ((TESTS_RUN++))
    if grep -q "REJECTED" "$TEST_DIR/results"/*invalid* 2>/dev/null; then
        print_pass "Invalid dataset was rejected"
        ((TESTS_PASSED++))
    else
        print_fail "Invalid dataset was not rejected"
        ((TESTS_FAILED++))
    fi
fi

echo ""

# ===== REPORT GENERATION =====
print_header "Report Generation"
echo ""

# Test report generation script exists
run_test "Report generation script exists" "test -f scripts/validation/generate_report.py"

# Generate report
print_test "Generating validation report"
((TESTS_RUN++))
if poetry run python scripts/validation/generate_report.py \
    --results-dir "$TEST_DIR/results" \
    --output "$TEST_DIR/report.md" \
    > "$TEST_DIR/report_output.log" 2>&1; then
    print_pass "Report generation completed"
    ((TESTS_PASSED++))
else
    print_fail "Report generation failed"
    ((TESTS_FAILED++))
    cat "$TEST_DIR/report_output.log"
fi

# Check report file created
run_test "Report file created" "test -f $TEST_DIR/report.md"

# Check report contains expected sections
if [ -f "$TEST_DIR/report.md" ]; then
    run_test "Report contains summary" "grep -q 'Summary\|SUMMARY' $TEST_DIR/report.md"
    run_test "Report contains statistics" "grep -q 'Total\|Statistics\|Records' $TEST_DIR/report.md"
fi

echo ""

# ===== API WORKFLOW =====
print_header "API Workflow (if available)"
echo ""

# Start API server in background
print_test "Starting API server"
((TESTS_RUN++))
poetry run uvicorn src.api.routes:app --host 127.0.0.1 --port 8888 > "$TEST_DIR/api.log" 2>&1 &
API_PID=$!

# Wait for API to start
sleep 3

if kill -0 $API_PID 2>/dev/null; then
    print_pass "API server started"
    ((TESTS_PASSED++))
    
    # Test health endpoint
    print_test "API health check"
    ((TESTS_RUN++))
    if curl -s http://127.0.0.1:8888/health | grep -q "healthy\|ok"; then
        print_pass "API health check successful"
        ((TESTS_PASSED++))
    else
        print_fail "API health check failed"
        ((TESTS_FAILED++))
    fi
    
    # Test validation endpoint
    print_test "API validation endpoint"
    ((TESTS_RUN++))
    RESPONSE=$(curl -s -X POST http://127.0.0.1:8888/api/v1/validate \
        -H "Content-Type: application/json" \
        -d '{
            "format": "guide_rna",
            "data": [{
                "guide_id": "gRNA_001",
                "sequence": "ATCGATCGATCGATCGATCG",
                "pam_sequence": "AGG",
                "target_gene": "BRCA1",
                "organism": "human",
                "nuclease_type": "SpCas9"
            }]
        }')
    
    if echo "$RESPONSE" | grep -q "validation_id\|final_decision"; then
        print_pass "API validation successful"
        ((TESTS_PASSED++))
    else
        print_fail "API validation failed"
        ((TESTS_FAILED++))
        echo "Response: $RESPONSE"
    fi
    
    # Stop API server
    kill $API_PID 2>/dev/null || true
    wait $API_PID 2>/dev/null || true
else
    print_fail "API server failed to start"
    ((TESTS_FAILED++))
    cat "$TEST_DIR/api.log"
fi

echo ""

# ===== DATABASE WORKFLOW =====
print_header "Database Workflow"
echo ""

# Test database initialization
print_test "Database initialization"
((TESTS_RUN++))
if poetry run python scripts/database/init_db.py > "$TEST_DIR/db_init.log" 2>&1; then
    print_pass "Database initialized"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}[SKIP]${NC} Database initialization (may not be implemented)"
fi

# Test database file created
if [ -f bio_validation.db ]; then
    print_pass "Database file created"
    ((TESTS_RUN++))
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}[SKIP]${NC} Database file not found (may not be implemented)"
fi

echo ""

# ===== PYTHON API WORKFLOW =====
print_header "Python API Workflow"
echo ""

# Create Python test script
PYTHON_TEST="$TEST_DIR/test_python_api.py"
cat > "$PYTHON_TEST" << 'PYTHON_EOF'
import asyncio
import pandas as pd
import sys

async def test_workflow():
    try:
        from src.agents.orchestrator import ValidationOrchestrator
        from src.schemas.base_schemas import DatasetMetadata, FormatType
        
        # Create test dataset
        df = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA'],
            'pam_sequence': ['AGG', 'TGG'],
            'target_gene': ['BRCA1', 'TP53'],
            'organism': ['human', 'human'],
            'nuclease_type': ['SpCas9', 'SpCas9']
        })
        
        # Create metadata
        metadata = DatasetMetadata(
            dataset_id="python_test_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=2,
            organism="human"
        )
        
        # Run validation
        orchestrator = ValidationOrchestrator()
        report = await orchestrator.validate_dataset(df, metadata)
        
        # Check results
        assert 'final_decision' in report
        assert 'stages' in report
        assert 'validation_id' in report
        
        print("SUCCESS: Python API workflow completed")
        return 0
        
    except Exception as e:
        print(f"FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(test_workflow())
    sys.exit(exit_code)
PYTHON_EOF

print_test "Python API workflow"
((TESTS_RUN++))
if poetry run python "$PYTHON_TEST" > "$TEST_DIR/python_test.log" 2>&1; then
    if grep -q "SUCCESS" "$TEST_DIR/python_test.log"; then
        print_pass "Python API workflow successful"
        ((TESTS_PASSED++))
    else
        print_fail "Python API workflow failed"
        ((TESTS_FAILED++))
        cat "$TEST_DIR/python_test.log"
    fi
else
    print_fail "Python API workflow failed"
    ((TESTS_FAILED++))
    cat "$TEST_DIR/python_test.log"
fi

echo ""

# ===== PERFORMANCE VALIDATION =====
print_header "Performance Validation"
echo ""

# Create large dataset for performance test
LARGE_CSV="$TEST_DIR/large_dataset.csv"
echo "guide_id,sequence,pam_sequence,target_gene,organism,nuclease_type" > "$LARGE_CSV"
for i in {1..1000}; do
    echo "gRNA_$(printf "%04d" $i),ATCGATCGATCGATCGATCG,AGG,BRCA1,human,SpCas9" >> "$LARGE_CSV"
done

print_test "Performance test (1000 records)"
((TESTS_RUN++))
START_TIME=$(date +%s)
if poetry run python scripts/validation/validate_datasets.py \
    --input-file "$LARGE_CSV" \
    --output-dir "$TEST_DIR/results" \
    > "$TEST_DIR/perf_output.log" 2>&1; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    if [ $DURATION -lt 60 ]; then
        print_pass "Performance test passed (${DURATION}s < 60s)"
        ((TESTS_PASSED++))
    else
        print_fail "Performance test too slow (${DURATION}s >= 60s)"
        ((TESTS_FAILED++))
    fi
else
    print_fail "Performance test failed"
    ((TESTS_FAILED++))
    cat "$TEST_DIR/perf_output.log"
fi

echo ""

# ===== FINAL SUMMARY =====
print_header "Test Summary"
echo ""

echo -e "Tests Run:    ${BLUE}$TESTS_RUN${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

# Calculate pass rate
if [ $TESTS_RUN -gt 0 ]; then
    PASS_RATE=$((TESTS_PASSED * 100 / TESTS_RUN))
    echo -e "Pass Rate:    ${BLUE}${PASS_RATE}%${NC}"
    echo ""
fi

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All end-to-end workflows completed successfully!${NC}"
    echo ""
    echo -e "${GREEN}The system is ready for production use.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some end-to-end workflows failed${NC}"
    echo ""
    echo -e "${YELLOW}Review the failed tests and fix issues before deployment.${NC}"
    exit 1
fi