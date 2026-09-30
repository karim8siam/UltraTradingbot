#!/usr/bin/env bash
# ==============================================================================
# UltraTradingBot Suite - Master Status Monitor
# Displays live process and PID status for all 10 engines and daily screener.
# ==============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$ROOT_DIR/.pids"

echo "================================================================================"
echo "📊 ULTRA TRADING BOT SUITE - LIVE PROCESS STATUS"
echo "================================================================================"
printf "%-32s %-10s %-12s %-10s\n" "ENGINE / SERVICE" "PID" "STATUS" "MEM / CPU"
echo "--------------------------------------------------------------------------------"

services=(
    "daily_screener"
    "engine_1"
    "engine_2"
    "engine_3"
    "engine_4"
    "engine_5"
    "engine_6"
    "engine_7"
    "engine_8"
    "engine_9"
    "engine_10"
)

for svc in "${services[@]}"; do
    pid_file="$PID_DIR/$svc.pid"
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            stats=$(ps -p "$pid" -o %cpu,%mem | tail -n 1)
            printf "%-32s %-10s \033[0;32m%-12s\033[0m %-10s\n" "$svc" "$pid" "RUNNING" "$stats"
        else
            printf "%-32s %-10s \033[0;31m%-12s\033[0m %-10s\n" "$svc" "$pid" "DEAD/STOPPED" "-"
        fi
    else
        printf "%-32s %-10s \033[0;33m%-12s\033[0m %-10s\n" "$svc" "-" "OFFLINE" "-"
    fi
done

echo "================================================================================"
