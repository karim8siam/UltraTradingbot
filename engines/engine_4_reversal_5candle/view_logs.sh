#!/usr/bin/env bash
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
tail -f "$SRC_DIR/bot.log"
