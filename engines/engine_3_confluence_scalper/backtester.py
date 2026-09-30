import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import SYMBOLS, TIMEFRAME, LEVERAGE, MAX_RISK_PER_TRADE, FEE_RATE, ATR_SL_MULT, ATR_TP_MULT, MAX_HOLD_CANDLES, MIN_SCORE
from binance_client import BinanceClient
from indicators import calc_all_indicators
from strategy import evaluate_candle
from risk_manager import RiskManager

def run_symbol_backtest(client, symbol, timeframe, sl_mult, tp_mult, max_hold, min_score):
    candles = client.fetch_klines(symbol, interval=timeframe, limit=1000)
    if not klines_ok(candles):
        return None

    data = calc_all_indicators(candles, timeframe=timeframe)
    if not data:
        return None

    trades = []
    n = len(candles)
    in_pos = False
    pos_type, entry_p, tp_p, sl_p, entry_i, score_v = None, 0, 0, 0, 0, 0

    for i in range(60, n):
        c = data['candles'][i]
        if in_pos:
            bars_held = i - entry_i
            exit_p, exit_r = None, None
            if pos_type == "LONG":
                if c['high'] >= tp_p and c['low'] <= sl_p:
                    exit_p, exit_r = sl_p, "SL"
                elif c['high'] >= tp_p:
                    exit_p, exit_r = tp_p, "TP"
                elif c['low'] <= sl_p:
                    exit_p, exit_r = sl_p, "SL"
                elif bars_held >= max_hold:
                    exit_p, exit_r = c['close'], "TIMEOUT"

                if exit_r:
                    raw = (exit_p - entry_p) / entry_p
                    trades.append({
                        'symbol': symbol, 'type': 'LONG',
                        'entry_time': data['candles'][entry_i]['time'],
                        'exit_time': c['time'], 'entry_price': entry_p,
                        'exit_price': exit_p, 'sl_price': sl_p, 'tp_price': tp_p,
                        'score': score_v, 'raw_ret': raw, 'reason': exit_r
                    })
                    in_pos = False

            elif pos_type == "SHORT":
                if c['low'] <= tp_p and c['high'] >= sl_p:
                    exit_p, exit_r = sl_p, "SL"
                elif c['low'] <= tp_p:
                    exit_p, exit_r = tp_p, "TP"
                elif c['high'] >= sl_p:
                    exit_p, exit_r = sl_p, "SL"
                elif bars_held >= max_hold:
                    exit_p, exit_r = c['close'], "TIMEOUT"

                if exit_r:
                    raw = (entry_p - exit_p) / entry_p
                    trades.append({
                        'symbol': symbol, 'type': 'SHORT',
                        'entry_time': data['candles'][entry_i]['time'],
                        'exit_time': c['time'], 'entry_price': entry_p,
                        'exit_price': exit_p, 'sl_price': sl_p, 'tp_price': tp_p,
                        'score': score_v, 'raw_ret': raw, 'reason': exit_r
                    })
                    in_pos = False

        if not in_pos and i < n - 1:
            eval_res = evaluate_candle(data, i)
            atr = eval_res['atr']
            l_s = eval_res['long_score']
            s_s = eval_res['short_score']

            if l_s >= min_score and s_s < min_score:
                in_pos, pos_type, entry_p, score_v = True, "LONG", c['close'], l_s
                tp_p = entry_p + (tp_mult * atr)
                sl_p = entry_p - (sl_mult * atr)
                entry_i = i
            elif s_s >= min_score and l_s < min_score:
                in_pos, pos_type, entry_p, score_v = True, "SHORT", c['close'], s_s
                tp_p = entry_p - (tp_mult * atr)
                sl_p = entry_p + (sl_mult * atr)
                entry_i = i

    return trades

def klines_ok(candles):
    return candles is not None and len(candles) >= 150

def run_portfolio_simulation(all_trades, initial_capital=10000.0, max_risk=MAX_RISK_PER_TRADE, leverage=LEVERAGE):
    sorted_trades = sorted(all_trades, key=lambda t: t['entry_time'])
    equity = initial_capital
    peak = initial_capital
    max_dd = 0.0
    simulated = []

    for t in sorted_trades:
        entry = t['entry_price']
        sl = t['sl_price']
        sl_pct = abs(entry - sl) / entry
        if sl_pct <= 0:
            continue

        target_risk = equity * max_risk
        pos_size = min(target_risk / sl_pct, equity * leverage)

        gross = pos_size * t['raw_ret']
        fees = pos_size * (FEE_RATE * 2)
        net = gross - fees

        equity += net
        equity = max(equity, 0.0)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

        simulated.append({'net': net, 'is_win': net > 0, 'reason': t['reason'], 'symbol': t['symbol']})
        if equity <= 0:
            break

    total = len(simulated)
    wins = [x for x in simulated if x['is_win']]
    losses = [x for x in simulated if not x['is_win']]
    wr = len(wins) / total * 100 if total > 0 else 0
    gp = sum(x['net'] for x in wins)
    gl = abs(sum(x['net'] for x in losses)) if losses else 1e-9
    pf = gp / gl if gl > 0 else 0

    return {
        'initial_capital': initial_capital,
        'final_equity': round(equity, 2),
        'total_gain_pct': round((equity - initial_capital) / initial_capital * 100, 2),
        'max_dd_pct': round(max_dd, 2),
        'total_trades': total,
        'win_rate': round(wr, 2),
        'profit_factor': round(pf, 2),
        'tp_hits': sum(1 for x in simulated if x['reason'] == 'TP'),
        'sl_hits': sum(1 for x in simulated if x['reason'] == 'SL'),
        'timeout_hits': sum(1 for x in simulated if x['reason'] == 'TIMEOUT')
    }

def main():
    parser = argparse.ArgumentParser(description="Backtest Engine 3 (Confluence Scalper)")
    parser.add_argument("--timeframe", default=TIMEFRAME, help="Candle timeframe (5m, 15m, 30m)")
    parser.add_argument("--sl_mult", type=float, default=ATR_SL_MULT, help="ATR SL multiplier")
    parser.add_argument("--tp_mult", type=float, default=ATR_TP_MULT, help="ATR TP multiplier")
    parser.add_argument("--max_hold", type=int, default=MAX_HOLD_CANDLES, help="Max candles to hold")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial capital in USDT")
    args = parser.parse_args()

    print("=" * 80)
    print(f"📊 BACKTESTING ENGINE 3 ACROSS {len(SYMBOLS)} CLEAN TOP CRYPTO PAIRS")
    print(f"Timeframe: {args.timeframe} | SL: {args.sl_mult}x ATR | TP: {args.tp_mult}x ATR | Hold: {args.max_hold} candles")
    print(f"Risk per Trade: {MAX_RISK_PER_TRADE * 100:.1f}% | Leverage: {LEVERAGE}x Isolated | Capital: ${args.capital:,.2f}")
    print("=" * 80)

    client = BinanceClient()
    all_trades = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(run_symbol_backtest, client, s, args.timeframe, args.sl_mult, args.tp_mult, args.max_hold, MIN_SCORE): s for s in SYMBOLS}
        for f in as_completed(futs):
            res = f.result()
            if res:
                all_trades.extend(res)

    results = run_portfolio_simulation(all_trades, initial_capital=args.capital)
    print("\n" + "=" * 50)
    print("RESULTS SUMMARY:")
    print(f"Total Trades Executed : {results['total_trades']}")
    print(f"Overall Win Rate      : {results['win_rate']:.2f}%")
    print(f"Profit Factor         : {results['profit_factor']:.2f}")
    print(f"Take-Profit Hits      : {results['tp_hits']}")
    print(f"Stop-Loss Hits        : {results['sl_hits']}")
    print(f"Timeout Exits         : {results['timeout_hits']}")
    print(f"Initial Capital       : ${results['initial_capital']:,.2f}")
    print(f"Final Equity          : ${results['final_equity']:,.2f}")
    print(f"Total Gain / Loss     : {results['total_gain_pct']:+.2f}%")
    print(f"Maximum Drawdown      : {results['max_dd_pct']:.2f}%")
    print("=" * 50)

if __name__ == "__main__":
    main()
