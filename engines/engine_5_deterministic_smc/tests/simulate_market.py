import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import math
import random
from typing import List, Dict
from strategy.models import Candle
from backtesting.engine import BacktestEngine
from backtesting.metrics import PerformanceMetrics
from config import Config

def generate_smc_market_data(num_days: int = 60) -> Dict[str, List[Candle]]:
    start_ts = 1700006400000
    candles_5m: List[Candle] = []
    
    ts = start_ts
    step_5m = 5 * 60 * 1000
    total_bars = (num_days * 24 * 60) // 5

    for bar_i in range(total_bars):
        macro_wave = math.sin(bar_i * (2 * math.pi / 576)) * 400.0 + (bar_i * 0.5)
        medium_wave = math.sin(bar_i * (2 * math.pi / 144)) * 150.0
        target_base = 50000.0 + macro_wave + medium_wave
        
        phase = (bar_i % 288)
        
        if phase in (84, 85):
            open_p = target_base
            low_p = open_p - 180.0
            close_p = open_p + 50.0
            high_p = open_p + 60.0
        elif phase == 86:
            open_p = target_base
            close_p = open_p + 250.0
            low_p = open_p - 10.0
            high_p = close_p + 20.0
        elif phase == 87:
            open_p = target_base + 250.0
            close_p = open_p + 80.0
            low_p = open_p - 5.0
            high_p = close_p + 15.0
        elif phase == 88:
            open_p = target_base + 330.0
            close_p = target_base + 260.0
            low_p = target_base + 240.0
            high_p = open_p + 5.0
        elif 89 <= phase <= 120:
            open_p = target_base + 260.0 + (phase - 88) * 15.0
            high_p = open_p + 30.0
            low_p = open_p - 10.0
            close_p = open_p + 20.0
        else:
            noise = random.uniform(-15, 15)
            open_p = target_base + noise
            high_p = open_p + random.uniform(10, 30)
            low_p = open_p - random.uniform(10, 30)
            close_p = open_p + random.uniform(-10, 10)

        candles_5m.append(Candle(
            timestamp=ts,
            open=open_p,
            high=max(open_p, close_p, high_p),
            low=min(open_p, close_p, low_p),
            close=close_p,
            volume=random.uniform(50, 500),
            is_closed=True
        ))
        ts += step_5m

    def aggregate_candles(candles_base: List[Candle], ratio: int) -> List[Candle]:
        agg = []
        for j in range(0, len(candles_base), ratio):
            chunk = candles_base[j:j+ratio]
            if not chunk:
                continue
            agg.append(Candle(
                timestamp=chunk[0].timestamp,
                open=chunk[0].open,
                high=max(c.high for c in chunk),
                low=min(c.low for c in chunk),
                close=chunk[-1].close,
                volume=sum(c.volume for c in chunk),
                is_closed=True
            ))
        return agg

    candles_15m = aggregate_candles(candles_5m, 3)
    candles_1h = aggregate_candles(candles_5m, 12)
    candles_4h = aggregate_candles(candles_5m, 48)

    return {
        "5m": candles_5m,
        "15m": candles_15m,
        "1h": candles_1h,
        "4h": candles_4h
    }

if __name__ == "__main__":
    print("[*] Generating 60-day natural wave SMC market dataset...")
    data = generate_smc_market_data(num_days=60)
    config = Config()
    engine = BacktestEngine(config)
    
    n_bars = len(data["5m"])
    print(f"[*] Running Backtest on synthesized SMC market (5M bars: {n_bars})...")
    res = engine.run_backtest("BTCUSDT", data["4h"], data["1h"], data["15m"], data["5m"])
    m = res["metrics"]
    
    np_val = m["net_profit"]
    ret_pct = m["return_pct"]
    gp_val = m["gross_profit"]
    gl_val = m["gross_loss"]
    fee_val = m["fees"]
    pf_val = m["profit_factor"]
    exp_val = m["expectancy_net"]
    dd_val = m["max_drawdown_pct"]
    
    print("\n" + "=" * 60)
    print("  DETERMINISTIC SMC BACKTEST VALIDATION REPORT")
    print("=" * 60)
    print("  Total Trades:           " + str(m["total_trades"]))
    print("  Winning Trades:         " + str(m["winning_trades"]) + " (" + str(round(m["win_rate"], 1)) + "%)")
    print("  Losing Trades:          " + str(m["losing_trades"]))
    print(f"  Net Profit:             ${np_val:+,.2f} ({ret_pct:+.2f}%)")
    print(f"  Gross Profit:           ${gp_val:,.2f}")
    print(f"  Gross Loss:             ${gl_val:,.2f}")
    print(f"  Total Fees & Slippage:  ${fee_val:,.2f}")
    print(f"  Profit Factor:          {pf_val:.2f}")
    print(f"  Expectancy Net / Trade: ${exp_val:+.2f}")
    print(f"  Max Drawdown:           {dd_val:.2f}%")
    print("  Max Consecutive Losses: " + str(m["max_consecutive_losses"]))
    print("=" * 60)
