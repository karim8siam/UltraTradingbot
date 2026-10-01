#!/usr/bin/env bash
# ==============================================================================
# UltraTradingBot Suite - One-Click Production Updater
# Pulls latest updates from GitHub, safely hot-reloads all engines and SaaS portal.
# Zero data loss (Neon database remains intact and untouched).
# ==============================================================================

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "================================================================================"
echo "🔄 UPDATING ULTRA TRADING BOT SUITE TO LATEST PRODUCTION VERSION"
echo "================================================================================"

# 1. Pull latest code from GitHub
echo "Fetching latest changes from origin/main..."
git pull origin main

# 2. Safely stop currently running processes
echo "Stopping existing services..."
./stop_all_local.sh

# 3. Ensure dependencies are up to date
echo "Verifying Python dependencies..."
pip3 install -q -r <(echo "
fastapi
uvicorn
pydantic
requests
cryptography
python-dotenv
psycopg[binary]
psycopg-pool
ccxt
numpy
pandas
scikit-learn
") || true

# 4. Relaunch all 12 services
echo "Relaunching all services..."
./launch_all_local.sh

# 5. Display live status
sleep 2
echo "Update complete! Process status:"
./status_all.sh
