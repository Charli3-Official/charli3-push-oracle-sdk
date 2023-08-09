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

# Remove content of directories if they exist
if [ -d "./wallets" ]; then
    rm -rf ./wallets/*
fi
if [ -d "./db" ]; then
    rm -rf ./db/*
fi

# Create directories if they don't exist
mkdir -p ./wallets
mkdir -p ./db

# Start the local cluster and dump the output to JSON
local-cluster -n 9 \
    --dump-info-json ./local-cluster-info.json \
    -d ./wallets/ \
    --ada 200 \
    --utxos 5  \
    -s 1s -e 3600 \
    > /dev/null 2>&1 &

# Save the PID of the local-cluster process
local_cluster_pid=$!

echo "Running local-cluster ..."

# Give it some time to start up
sleep 5

# Extract the temporal directory from the JSON file using jq (a command-line JSON processor)
temp_dir=$(dirname $(jq -r '.ciNodeSocket' ./local-cluster-info.json))

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
poetry run pytest tests

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
