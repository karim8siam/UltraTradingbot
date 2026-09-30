#!/usr/bin/env bash
PLIST_NAME="com.binance.tradingbot.plist"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/Library/LaunchAgents"

mkdir -p "$TARGET_DIR"

# Unload previous service if exists
launchctl unload "$TARGET_DIR/$PLIST_NAME" 2>/dev/null || true

# Copy plist to LaunchAgents directory
cp "$SRC_DIR/$PLIST_NAME" "$TARGET_DIR/$PLIST_NAME"

# Load the daemon
launchctl load "$TARGET_DIR/$PLIST_NAME"

echo "=================================================="
echo " Binance Trading Bot Daemon Successfully Installed!"
echo " It will run in background and auto-start on boot."
echo " Log file: $SRC_DIR/bot.log"
echo "=================================================="
