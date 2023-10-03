#!/usr/bin/env bash

set -e
set -x

# Function to kill processes
kill_processes() {
    echo "Shutting down the cluster..."
    if kill -0 $local_cluster_pid > /dev/null 2>&1; then
        kill $local_cluster_pid
    fi
    if kill -0 $ogmios_pid > /dev/null 2>&1; then
        kill $ogmios_pid
    fi
    if kill -0 $kupo_pid > /dev/null 2>&1; then
        kill $kupo_pid
    fi
    exit 0
}
# Trap the SIGINT signal and call the function to kill processes
trap 'kill_processes' SIGINT SIGTERM

# Remove content of directories if they exist
if [ -d "$PWD/wallets" ]; then
    rm -rf "$PWD"/wallets/*
fi
if [ -d "$PWD/db" ]; then
    rm -rf "$PWD"/db/*
fi

# Create directories if they don't exist
mkdir -p "$PWD"/wallets
mkdir -p "$PWD"/db

# Start the local cluster and dump the output to JSON
local-cluster -n 9 \
    --dump-info-json "$PWD"/local-cluster-info.json \
    -d "$PWD"/wallets/ \
    --ada 10000 \
    --utxos 5  \
    -s 1s -e 43200 \
    > /dev/null 2>&1 &

# Save the PID of the local-cluster process
local_cluster_pid=$!

echo "Running local-cluster ..."

# Give it some time to start up
sleep 10

if [ ! -f "$PWD/local-cluster-info.json" ]; then
    echo "Error: JSON file does not exist"
    exit 1
fi

# Extract the temporal directory from the JSON file using jq (a command-line JSON processor)
temp_dir=$(dirname $(jq -r '.ciNodeSocket' "$PWD/local-cluster-info.json"))

# Run the other commands with the extracted directory
ogmios --node-socket $temp_dir/node.socket \
    --node-config $temp_dir/node.config > /dev/null 2>&1 &

ogmios_pid=$!

echo "Running ogmios ..."

# Give it some time to start up
sleep 5

kupo --node-socket $temp_dir/node.socket \
    --node-config $temp_dir/node.config \
    --workdir ./db --match "*" \
    --since origin > /dev/null 2>&1 &

kupo_pid=$!

echo "Running kupo ..."

# Give it some time to start up
sleep 5


# Tests
# For all tests
# poetry run pytest tests

# Function to run a specific test pattern
run_test() {
    local test_pattern="$1"
    poetry run pytest tests -v -k "$test_pattern"
}

# Function to run a test pattern multiple times with a delay
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

# For the TestAggregate, we want to run it multiple times with a delay
# The delay ensures any side effects from previous runs are cleared up
run_test_multiple_times "TestAggregate" 2 3m

run_test "TestAddFunds or TestEditSettings or TestAddNodes or TestRemoveNodes or TestNodeCollect or TestPlatformCollect or TestOracleClose"

# For aggregation-tx
# poetry run pytest tests -v -k "TestDeployment or TestAggregate"

# For aggregation-tx in a loop
# poetry run pytest tests -v -k "TestDeployment"
# for i in {1..100}; do
#   echo "Running test iteration $i"
#   poetry run pytest tests -v -k "TestAggregate"
#   sleep 3m
# done

# echo "Press Ctrl + C to stop"
# while true; do sleep 1; done

# After tests finish, kill the background services
if kill -0 $local_cluster_pid > /dev/null 2>&1; then
    kill $local_cluster_pid
fi
if kill -0 $ogmios_pid > /dev/null 2>&1; then
    kill $ogmios_pid
fi
if kill -0 $kupo_pid > /dev/null 2>&1; then
    kill $kupo_pid
fi

exit 0
