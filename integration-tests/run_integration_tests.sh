#!/usr/bin/env bash

set -e  # Exit on any command failure
set -x  # Print each command before executing it

# Function to kill processes
kill_processes() {
  echo "Shutting down the cluster..."
  ./bin/devkit.sh stop

  # Preserve the exit code from tests
  exit $test_result
}

# Trap the SIGINT, SIGTERM, and EXIT signals and call the function to kill processes
trap 'kill_processes' SIGINT SIGTERM EXIT

# Start the node in the background
./bin/devkit.sh stop && ./bin/devkit.sh start create-node -o --start -e 4000 >/dev/null 2>&1 &
# Wait for the node to start
echo "Waiting for the node to start..."
sleep 60

# Tests
run_test() {
  local test_pattern="$1"
  poetry run pytest tests -v -k "$test_pattern"

  # Capture the exit code of the test
  test_result=$?

  # Exit if the test fails
  if [ $test_result -ne 0 ]; then
    echo "Test pattern $test_pattern failed."
    exit $test_result
  fi
}

run_test_multiple_times() {
  local test_pattern="$1"
  local count="$2"
  local delay="$3"

  for i in $(seq 1 "$count"); do
    echo "Running test iteration $i for pattern: $test_pattern"
    run_test "$test_pattern"
    sleep "$delay"
  done
}

# Execute tests
run_test "TestDeployment"
run_test "TestCreateReferenceScript"

run_test_multiple_times "TestAggregate" 1 10

run_test "TestAddFunds or TestEditSettings or TestAddNodes or TestRemoveNodes or TestNodeCollect or TestPlatformCollect"

run_test_multiple_times "TestAggregate" 1 10

run_test "TestOracleClose"

run_test "TestMultisigDeployment"
run_test "TestMultisigReferenceScript"
run_test "TestMultisigRemoveNodes"

# Stop the cluster (this will also be handled by kill_processes on EXIT)
./bin/devkit.sh stop

# Exit with the result of the last test
exit $test_result
