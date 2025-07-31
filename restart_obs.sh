#!/bin/bash

echo "🔁 Gracefully terminating OBS..."

# Step 1: Find the non-defunct OBS PID
PID=$(ps -eo pid,comm,state | grep -w obs | grep -v defunct | awk '$3 != "Z" {print $1}' | head -n 1)

if [ -z "$PID" ]; then
    echo "❌ OBS is not running or only defunct."
    exit 1
fi

echo "🧪 Sending SIGINT to PID $PID"
kill -SIGINT "$PID"
sleep 2

# Step 2: Check if still running
if ps -p "$PID" > /dev/null; then
    echo "⚠️ Still running. Sending SIGTERM..."
    kill -SIGTERM "$PID"
    sleep 3
fi

# Step 3: Give it up to 10 seconds
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null; then
        echo "✅ OBS has shut down cleanly."
        exit 0
    fi
    sleep 1
done

# Step 4: Force kill
echo "💣 Still running. Sending SIGKILL..."
kill -9 "$PID"
echo "🧼 OBS force-killed. systemd will restart it."
