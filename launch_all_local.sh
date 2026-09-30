#!/usr/bin/env bash
# ==============================================================================
# UltraTradingBot Suite - Master Local Launcher
# Launches all 10 fully decoupled independent trading engines + Daily Screener
# concurrently in the background with dedicated logs and PID tracking.
# ==============================================================================

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$ROOT_DIR/.pids"
LOG_DIR="$ROOT_DIR/logs"

mkdir -p "$PID_DIR" "$LOG_DIR"

echo "================================================================================"
echo "🚀 LAUNCHING ALL 10 INDEPENDENT ULTRA TRADING ENGINES + DAILY SCREENER"
echo "================================================================================"
echo "Mode: Each engine runs as a completely decoupled, standalone process."
echo "Logs Directory: $LOG_DIR"
echo "PID Directory:  $PID_DIR"
echo "--------------------------------------------------------------------------------"

# 0. Daily Screener (24h Midnight Evaluator)
echo "Starting [Daily Screener]..."
cd "$ROOT_DIR/screener"
nohup python3 -u daily_screener.py > "$LOG_DIR/screener.log" 2>&1 &
echo $! > "$PID_DIR/daily_screener.pid"

# SaaS Client Web Portal & API (Port 8080)
echo "Starting [SaaS Web Portal on http://localhost:8080]..."
cd "$ROOT_DIR/saas"
nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8080 > "$LOG_DIR/saas_platform.log" 2>&1 &
echo $! > "$PID_DIR/saas_platform.pid"

# 1. Engine 1: Multi-Regime ML
echo "Starting [Engine 1: Multi-Regime ML]..."
cd "$ROOT_DIR/engines/engine_1_multiregime_ml"
nohup python3 -u bot.py > "$LOG_DIR/engine_1.log" 2>&1 &
echo $! > "$PID_DIR/engine_1.pid"

# 2. Engine 2: 15M 3-Candle Momentum
echo "Starting [Engine 2: 3-Candle Momentum]..."
cd "$ROOT_DIR/engines/engine_2_momentum_3candle"
nohup python3 -u bot.py > "$LOG_DIR/engine_2.log" 2>&1 &
echo $! > "$PID_DIR/engine_2.pid"

# 3. Engine 3: 10-Point Confluence Scalper
echo "Starting [Engine 3: Confluence Scalper]..."
cd "$ROOT_DIR/engines/engine_3_confluence_scalper"
nohup python3 -u bot.py > "$LOG_DIR/engine_3.log" 2>&1 &
echo $! > "$PID_DIR/engine_3.pid"

# 4. Engine 4: 15M 5-Candle Reversal
echo "Starting [Engine 4: 5-Candle Reversal]..."
cd "$ROOT_DIR/engines/engine_4_reversal_5candle"
nohup python3 -u bot.py > "$LOG_DIR/engine_4.log" 2>&1 &
echo $! > "$PID_DIR/engine_4.pid"

# 5. Engine 5: Deterministic SMC
echo "Starting [Engine 5: Deterministic SMC]..."
cd "$ROOT_DIR/engines/engine_5_deterministic_smc"
nohup python3 -u main.py --mode dry-run > "$LOG_DIR/engine_5.log" 2>&1 &
echo $! > "$PID_DIR/engine_5.pid"

# 6. Engine 6: Fibonacci Pullback
echo "Starting [Engine 6: Fibonacci Pullback]..."
cd "$ROOT_DIR/engines/engine_6_fibonacci_pullback"
nohup python3 -u main.py --mode dry-run > "$LOG_DIR/engine_6.log" 2>&1 &
echo $! > "$PID_DIR/engine_6.pid"

# 7. Engine 7: Institutional FVG
echo "Starting [Engine 7: Institutional FVG]..."
cd "$ROOT_DIR/engines/engine_7_institutional_fvg"
nohup python3 -u live_daemon.py > "$LOG_DIR/engine_7.log" 2>&1 &
echo $! > "$PID_DIR/engine_7.pid"

# 8. Engine 8: GFS Multi-Timeframe
echo "Starting [Engine 8: GFS Multi-Timeframe]..."
cd "$ROOT_DIR/engines/engine_8_gfs_multitimeframe"
nohup python3 -u run_bot.py --mode LIVE --risk 0.02 --leverage 5 --max-positions 1 > "$LOG_DIR/engine_8.log" 2>&1 &
echo $! > "$PID_DIR/engine_8.pid"

# 9. Engine 9: Futures Swing
echo "Starting [Engine 9: Futures Swing]..."
cd "$ROOT_DIR/engines/engine_9_futures_swing"
nohup python3 -u main.py paper > "$LOG_DIR/engine_9.log" 2>&1 &
echo $! > "$PID_DIR/engine_9.pid"

# 10. Engine 10: Confluence 100-Pairs
echo "Starting [Engine 10: Confluence 100-Pairs]..."
cd "$ROOT_DIR/engines/engine_10_confluence_100pairs"
nohup python3 -u main.py > "$LOG_DIR/engine_10.log" 2>&1 &
echo $! > "$PID_DIR/engine_10.pid"

cd "$ROOT_DIR"
echo "--------------------------------------------------------------------------------"
echo "✅ ALL 10 ENGINES + DAILY SCREENER RUNNING CONCURRENTLY IN THE BACKGROUND!"
echo "Use './status_all.sh' to inspect live processes."
echo "Use './stop_all_local.sh' to terminate all engines."
echo "================================================================================"
