#!/bin/bash

terminate() {
    echo "Terminating processes..."
    kill -TERM "$child1" "$child2"
    wait
    exit 0
}

# Trap SIGTERM and SIGINT
trap terminate SIGTERM SIGINT

python3 pubsub_proxy.py &
child1=$!

python3 queryable_router.py &
child2=$!

# Wait for all background processes
wait
