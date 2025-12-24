#!/bin/bash
# Test script for hactl commands
# Tests all commands against live Home Assistant instance

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0
SKIPPED=0

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}hactl Command Integration Tests${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Function to test Python file for import errors
test_imports() {
    local file="$1"
    local name="$2"

    echo -n "Checking imports: $name ... "

    # Convert file path to module path (replace / with .)
    module_path="${file//\//.}"

    # Try to import the module and check for errors
    output=$(python3 -c "import sys; sys.path.insert(0, '.'); from ${module_path} import *" 2>&1)
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}OK${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        # Show the actual error
        echo "  Error: $(echo "$output" | grep -E '(ImportError|NameError|ModuleNotFoundError|SyntaxError)' | head -1)"
        ((FAILED++))
        return 1
    fi
}

# Function to run a test
run_test() {
    local test_name="$1"
    local command="$2"
    local expect_output="$3"

    echo -n "Testing: $test_name ... "

    # Run command and capture output and exit code
    output=$(eval "$command" 2>&1)
    exit_code=$?

    # Check if command succeeded
    if [ $exit_code -eq 0 ]; then
        # If we expect specific output, check for it
        if [ -n "$expect_output" ]; then
            if echo "$output" | grep -q "$expect_output"; then
                echo -e "${GREEN}PASS${NC}"
                ((PASSED++))
                return 0
            else
                echo -e "${RED}FAIL${NC} (missing expected output: $expect_output)"
                ((FAILED++))
                return 1
            fi
        else
            echo -e "${GREEN}PASS${NC}"
            ((PASSED++))
            return 0
        fi
    else
        echo -e "${RED}FAIL${NC} (exit code: $exit_code)"
        echo "  Error: $output"
        ((FAILED++))
        return 1
    fi
}

# Function to skip a test
skip_test() {
    local test_name="$1"
    local reason="$2"
    echo -e "Testing: $test_name ... ${YELLOW}SKIP${NC} ($reason)"
    ((SKIPPED++))
}

echo -e "${BLUE}=== Import Validation ===${NC}"

# Test all handler files can be imported without errors
for handler in hactl/handlers/*.py; do
    if [ -f "$handler" ] && [ "$(basename $handler)" != "__init__.py" ]; then
        module_path="${handler%.py}"
        module_name=$(basename "$handler" .py)
        test_imports "$module_path" "$module_name"
    fi
done

echo ""
echo -e "${BLUE}=== GET Commands ===${NC}"

# GET commands with table format (default)
run_test "hactl get devices" "hactl get devices" "Home Assistant Devices"
run_test "hactl get states" "hactl get states" "Home Assistant Entity States"
run_test "hactl get integrations" "hactl get integrations" "Configured Integrations"
run_test "hactl get services" "hactl get services" "Home Assistant Services"
run_test "hactl get automations" "hactl get automations" "Automations"
run_test "hactl get scripts" "hactl get scripts" "Scripts"
run_test "hactl get scenes" "hactl get scenes" "Scenes"
run_test "hactl get helpers" "hactl get helpers" "Helpers"
run_test "hactl get dashboards" "hactl get dashboards" "Dashboards"
skip_test "hactl get dashboards --url-path [dashboard/view]" "requires specific dashboard structure"
skip_test "hactl get dashboards --format validate --url-path [dashboard/view]" "requires specific dashboard structure"
run_test "hactl get calendars" "hactl get calendars" "Calendars"
run_test "hactl get cameras" "hactl get cameras" "Cameras"
run_test "hactl get media-players" "hactl get media-players" "Media Players"
run_test "hactl get persons-zones" "hactl get persons-zones" ""
run_test "hactl get home-structure" "hactl get home-structure" ""
run_test "hactl get events" "hactl get events" ""
run_test "hactl get history" "hactl get history" ""
run_test "hactl get activity" "hactl get activity" ""
run_test "hactl get todos" "hactl get todos" ""
run_test "hactl get notifications" "hactl get notifications" ""
run_test "hactl get templates" "hactl get templates" ""

echo ""
echo -e "${BLUE}=== GET Sensors by Type ===${NC}"

# Sensor types
run_test "hactl get sensors battery" "hactl get sensors battery" ""
run_test "hactl get sensors temperature" "hactl get sensors temperature" ""
run_test "hactl get sensors humidity" "hactl get sensors humidity" ""
run_test "hactl get sensors motion" "hactl get sensors motion" ""
run_test "hactl get sensors power" "hactl get sensors power" ""
run_test "hactl get sensors energy" "hactl get sensors energy" ""

echo ""
echo -e "${BLUE}=== Output Format Tests ===${NC}"

# Test different output formats
run_test "hactl get devices --format json" "hactl get devices --format json | head -5" ""
run_test "hactl get devices --format yaml" "hactl get devices --format yaml" "Home Assistant Devices"
run_test "hactl get devices --format detail" "hactl get devices --format detail" "Total Devices"
run_test "hactl get states --format json" "hactl get states --format json | head -5" ""
run_test "hactl get states --format csv" "hactl get states --format csv | head -5" ""

echo ""
echo -e "${BLUE}=== Domain Filtering Tests ===${NC}"

# Test domain filtering
run_test "hactl get states --domain light" "hactl get states --domain light" ""
run_test "hactl get states --domain sensor" "hactl get states --domain sensor" ""
run_test "hactl get states --domain switch" "hactl get states --domain switch" ""

echo ""
echo -e "${BLUE}=== BATTERY Commands ===${NC}"

# Battery commands
run_test "hactl battery list" "hactl battery list" ""
run_test "hactl battery list --exclude-mobile" "hactl battery list --exclude-mobile" ""
run_test "hactl battery check" "hactl battery check" ""

echo ""
echo -e "${BLUE}=== MEMORY Commands ===${NC}"

# Memory commands
run_test "hactl memory list" "hactl memory list" ""
skip_test "hactl memory add" "requires arguments"
skip_test "hactl memory show" "requires category argument"
skip_test "hactl memory edit" "requires file path"

# Test memory sync and verify all 17 CSV files are created
echo -n "Testing: hactl memory sync (creates 17 CSV files) ... "
# Create a temporary memory directory for testing
TEMP_MEMORY_DIR=$(mktemp -d)
# Run sync
hactl memory sync > /dev/null 2>&1
# Check if all 17 expected CSV files exist in memory/ directory
EXPECTED_FILES=(
    "devices.csv"
    "states.csv"
    "automations.csv"
    "dashboards.csv"
    "hacs.csv"
    "areas.csv"
    "integrations.csv"
    "scripts.csv"
    "scenes.csv"
    "templates.csv"
    "entity_relationships.csv"
    "automation_stats.csv"
    "service_capabilities.csv"
    "battery_health.csv"
    "energy_data.csv"
    "automation_context.csv"
    "persons_presence.csv"
)

MISSING_FILES=()
for file in "${EXPECTED_FILES[@]}"; do
    if [ ! -f "memory/$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    echo -e "${GREEN}PASS${NC} (all 17 CSV files created)"
    ((PASSED++))
else
    echo -e "${RED}FAIL${NC} (missing files: ${MISSING_FILES[*]})"
    ((FAILED++))
fi

echo ""
echo -e "${BLUE}=== UPDATE Commands ===${NC}"

# Update commands (skip - would modify HA)
skip_test "hactl update dashboard" "would modify Home Assistant"
skip_test "hactl update helper" "would modify Home Assistant"

echo ""
echo -e "${BLUE}=== K8S Commands ===${NC}"

# K8s commands - test if kubectl is available
if command -v kubectl &> /dev/null; then
    # Get namespace from environment or use default
    K8S_NAMESPACE="${K8S_NAMESPACE:-home-automation}"
    run_test "hactl k8s find-pod --namespace $K8S_NAMESPACE" "hactl k8s find-pod --namespace $K8S_NAMESPACE" ""
    run_test "hactl k8s get-config --help" "hactl k8s get-config --help" "Get Home Assistant configuration"
    run_test "hactl k8s put-config --help" "hactl k8s put-config --help" "Upload configuration"
    skip_test "hactl k8s get-config" "would download config (use --output for real use)"
    skip_test "hactl k8s put-config" "would modify kubernetes config"
    skip_test "hactl k8s update-config" "would modify kubernetes config"
else
    skip_test "hactl k8s find-pod" "kubectl not available"
    skip_test "hactl k8s get-config" "kubectl not available"
    skip_test "hactl k8s put-config" "kubectl not available"
    skip_test "hactl k8s update-config" "kubectl not available"
fi

echo ""
echo -e "${BLUE}=== Additional Tests ===${NC}"

# Test help and version
run_test "hactl --help" "hactl --help" "Usage: hactl"
run_test "hactl --version" "hactl --version" ""
run_test "hactl get --help" "hactl get --help" "Get resources from Home Assistant"

# Test error handling
echo -n "Testing: Invalid command ... "
output=$(hactl get invalid-command 2>&1)
if echo "$output" | grep -q "Error\|Usage"; then
    echo -e "${GREEN}PASS${NC} (properly handles invalid command)"
    ((PASSED++))
else
    echo -e "${RED}FAIL${NC} (should show error for invalid command)"
    ((FAILED++))
fi

echo ""
echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}================================${NC}"
echo -e "${GREEN}Passed:${NC}  $PASSED"
echo -e "${RED}Failed:${NC}  $FAILED"
echo -e "${YELLOW}Skipped:${NC} $SKIPPED"
echo -e "Total:   $((PASSED + FAILED + SKIPPED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the output above.${NC}"
    exit 1
fi
