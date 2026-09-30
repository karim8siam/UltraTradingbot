"""
Live Binance Market Diagnostic & 25-Pair Scanner
Fetches real-time Binance Futures data and diagnoses market structure, FVGs, and shift status.
"""

import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import BotConfig
from binance_client import BinanceFuturesClient
from indicators import calculate_atr
from trend_detector import detect_market_structure_bias, evaluate_htf_alignment
from fvg_engine import detect_fvgs_on_15m
from confirmation_engine import check_5m_confirmation
from setup_evaluator import evaluate_setup
from risk_manager import RiskManager


def run_live_diagnostics():
    config = BotConfig()
    client = BinanceFuturesClient(
        api_key=config.BINANCE_API_KEY,
        api_secret=config.BINANCE_API_SECRET,
        testnet=config.BINANCE_TESTNET
    )
    risk_mgr = RiskManager()

    print("\n" + "=" * 110)
    print(f"       BINANCE USDT-M FUTURES — REAL-TIME 25-PAIR LIVE MARKET DIAGNOSTIC")
    print(f"       Scan Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 110)

    # 1. Connection & Account Check
    print("\n[1] BINANCE API & LIVE ACCOUNT STATUS:")
    print("-" * 110)
    try:
        live_balance = client.get_account_balance()
        print(f"  ✅ API Connection        : ACTIVE & AUTHENTICATED")
        print(f"  ✅ Live USDT-M Futures Bal: ${live_balance:,.2f} USDT")
        print(f"  ✅ 1% Risk Allocation    : ${live_balance * 0.01:.4f} USDT per trade")
        print(f"  ✅ Leverage Setting      : {config.DEFAULT_LEVERAGE}x")
        print(f"  ✅ Session Filter        : 24/7 CONTINUOUS TRADING (Active Around the Clock)")
    except Exception as e:
        print(f"  ❌ API Connection Error: {str(e)}")
        return

    # 2. 25-Pair Market Scan
    print(f"\n[2] LIVE 25-PAIR MARKET CONDITION SCAN (MONITORING {len(config.SYMBOLS)} PAIRS):")
    print("=" * 110)
    print(f" {'Symbol':<10} | {'Price':<12} | {'4H Bias':<7} | {'1H Bias':<7} | {'15M FVG Status':<22} | {'Live Market Condition & Status'}")
    print("-" * 110)

    for sym in config.SYMBOLS:
        try:
            time.sleep(0.1)  # smooth pacing
            c4 = client.get_klines(sym, "4h", limit=50)
            c1 = client.get_klines(sym, "1h", limit=100)
            c15 = client.get_klines(sym, "15m", limit=150)
            c5 = client.get_klines(sym, "5m", limit=200)

            if not c4 or not c1 or not c15 or not c5:
                print(f" {sym:<10} | {'N/A':<12} | {'-':<7} | {'-':<7} | {'NO DATA':<22} | Incomplete klines")
                continue

            curr_price = c5[-1].close

            # 4H and 1H bias
            b4, _, _, _, _ = detect_market_structure_bias(c4, swing_length=2, timeframe="4h")
            b1, _, _, _, _ = detect_market_structure_bias(c1, swing_length=2, timeframe="1h")
            htf_dir, _, _ = evaluate_htf_alignment(c4, c1, swing_length=2)

            # 15M FVGs
            fvgs = detect_fvgs_on_15m(c15, sym)
            valid_fvgs = [f for f in fvgs if (htf_dir == "LONG" and f.is_bullish) or (htf_dir == "SHORT" and f.is_bearish)]

            fvg_str = "No Valid FVG"
            diag_reason = ""

            if not htf_dir:
                diag_reason = f"HTF Conflict (4H={b4.value[:4]}, 1H={b1.value[:4]}) -> Waiting for structural alignment"
            elif not valid_fvgs:
                diag_reason = f"HTF {htf_dir} aligned. Waiting for fresh 15M displacement FVG"
            else:
                latest_fvg = valid_fvgs[-1]
                fvg_type = "BULL" if latest_fvg.is_bullish else "BEAR"
                fvg_str = f"{fvg_type} [{latest_fvg.fvg_low:.2f}-{latest_fvg.fvg_high:.2f}]"

                # Check 5M confirmation
                sig = check_5m_confirmation(latest_fvg, c5)
                if not sig:
                    subsequent = [c for c in c5 if c.timestamp >= latest_fvg.created_timestamp]
                    age = len(subsequent)
                    if age > 50:
                        diag_reason = f"FVG Expired (age {age} > 50) -> Waiting for fresh FVG"
                    elif latest_fvg.is_bullish and c15[-1].close < latest_fvg.fvg_low:
                        diag_reason = f"Bullish FVG Invalidated (close below low) -> Waiting for fresh FVG"
                    elif latest_fvg.is_bearish and c15[-1].close > latest_fvg.fvg_high:
                        diag_reason = f"Bearish FVG Invalidated (close above high) -> Waiting for fresh FVG"
                    else:
                        diag_reason = f"FVG Valid. Waiting for pullback into zone & 5M shift"
                else:
                    setup = evaluate_setup(latest_fvg, sig, c15, c1, c4, b4, b1, curr_price)
                    if setup.is_valid:
                        diag_reason = f"🔥 ENTRY READY! ({setup.side} @ ${setup.entry_price:.4f}, Score: {setup.setup_score}, RR: {setup.rr:.2f})"
                    else:
                        diag_reason = f"Confirmed but filtered ({setup.rejection_reason}, Score: {setup.setup_score})"

            print(f" {sym:<10} | ${curr_price:<11.4f} | {b4.value[:4]:<7} | {b1.value[:4]:<7} | {fvg_str:<22} | {diag_reason}")

        except Exception as e:
            print(f" {sym:<10} | {'Error':<12} | {'-':<7} | {'-':<7} | {'-':<22} | {str(e)[:45]}")

    print("=" * 110 + "\n")


if __name__ == "__main__":
    run_live_diagnostics()
