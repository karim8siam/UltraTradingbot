#!/usr/bin/env bash
PLIST_NAME="com.binance.tradingbot.plist"
TARGET_DIR="$HOME/Library/LaunchAgents"

launchctl unload "$TARGET_DIR/$PLIST_NAME" 2>/dev/null || true
echo "Binance Trading Bot Daemon stopped."
