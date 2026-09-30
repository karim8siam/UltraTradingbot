#!/bin/bash
# Start Binance FVG Bot in background
cd "$(dirname "$0")"
nohup python3 live_daemon.py > /dev/null 2>&1 &
echo "Bot started in background (PID: $!). Monitoring logs at: bot_live.log"
echo "To view live logs: tail -f bot_live.log"
