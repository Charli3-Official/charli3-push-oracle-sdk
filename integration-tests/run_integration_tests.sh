#!/bin/bash
#
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

# Clean up the wallets and db directories
rm -rf ./wallets/*
rm -rf ./db/*

# Start the local cluster and dump the output to JSON
local-cluster -n 7 --dump-info-json ./local-cluster-info.json -d ./wallets/ --ada 10000 --utxos 4 --lovelace 9000000 -s 1s -e 300 > /dev/null 2>&1 &
# local-cluster -n 7 --dump-info-json ./local-cluster-info.json -d ./wallets/ --ada 10000 --utxos 4 --lovelace 9000000 -s 1s -e 300 &
# Save the PID of the local-cluster process
local_cluster_pid=$!

echo "Running local-cluster ..."

# Give it some time to start up
sleep 5

# Extract the temporal directory from the JSON file using jq (a command-line JSON processor)
temp_dir=$(dirname $(jq -r '.ciNodeSocket' ./local-cluster-info.json))

# Run the other commands with the extracted directory
ogmios --node-socket $temp_dir/node.socket --node-config $temp_dir/node.config > /dev/null 2>&1 &
echo "$temp_dir"
# ogmios --node-socket $temp_dir/node.socket --node-config $temp_dir/node.config &
ogmios_pid=$!

echo "Running ogmios ..."
# Give it some time to start up
sleep 3

kupo --node-socket $temp_dir/node.socket --node-config $temp_dir/node.config --workdir ./db --match "*" --since origin > /dev/null 2>&1 &
# kupo --node-socket $temp_dir/node.socket --node-config $temp_dir/node.config --workdir ./db --match "*" --since origin &
kupo_pid=$!

echo "Running kupo ..."

# Give it some time to start up
sleep 3

echo "Press Ctrl + C to stop"

# Now you can run your tests
# poetry run pytest tests

# kill $local_cluster_pid
# kill $ogmios_pid
# kill $kupo_pid
while true; do sleep 1; done
