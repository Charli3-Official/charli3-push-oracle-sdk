#!/usr/bin/env bash

set -e
set -x

# Function to kill processes
kill_processes() {
  echo "Shutting down the cluster..."
  ./bin/devkit.sh stop
  exit 0
}
# Trap the SIGINT signal and call the function to kill processes
trap 'kill_processes' SIGINT SIGTERM EXIT

# Start the node in the background
./bin/devkit.sh stop && ./bin/devkit.sh start create-node -o -e 4000 --start --era babbage >/dev/null 2>&1 &

sleep 60

# Tests
run_test() {
  local test_pattern="$1"
  poetry run pytest tests -v -k "$test_pattern"

  # Exit if the test fails
  if [ $? -ne 0 ]; then
    echo "Test pattern $test_pattern failed."
    exit 1
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

# Stop the cluster
./bin/devkit.sh stop

exit 0
