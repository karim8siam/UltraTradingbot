#!/usr/bin/env bash
# ==============================================================================
# UltraTradingBot Suite - Master Local Stopper
# Gracefully stops all 10 independent trading engines and the daily screener.
# ==============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$ROOT_DIR/.pids"

echo "================================================================================"
echo "🛑 STOPPING ALL ULTRA TRADING BOT PROCESSES"
echo "================================================================================"

if [ -d "$PID_DIR" ]; then
    for pid_file in "$PID_DIR"/*.pid; do
        if [ -f "$pid_file" ]; then
            name=$(basename "$pid_file" .pid)
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                echo "Terminating $name (PID: $pid)..."
                kill "$pid" 2>/dev/null || true
            else
                echo "$name (PID: $pid) is already stopped."
            fi
            rm -f "$pid_file"
        fi
    done
fi

echo "All engines stopped successfully."
echo "================================================================================"
