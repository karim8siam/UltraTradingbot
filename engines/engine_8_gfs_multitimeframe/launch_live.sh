#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Check if bot is already running
PID=$(pgrep -f "run_bot.py --mode LIVE")
if [ -n "$PID" ]; then
    echo "[!] GFS Bot is already running with PID: $PID"
    exit 0
fi

echo "[*] Launching Binance Futures GFS Bot in continuous background mode..."
nohup python3 -u run_bot.py --mode LIVE --risk 0.02 --leverage 5 --max-positions 1 > gfs_live.log 2>&1 &
NEW_PID=$!
echo "[+] GFS Bot started successfully! PID: $NEW_PID"
echo "[+] Live log stream: tail -f $DIR/gfs_live.log"
