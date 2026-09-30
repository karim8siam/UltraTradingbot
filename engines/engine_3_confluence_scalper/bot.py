import os
import sys
import time
import json
from datetime import datetime
from config import SYMBOLS, TIMEFRAME, MAX_HOLD_CANDLES, DRY_RUN, LEVERAGE
from binance_client import BinanceClient
from indicators import calc_all_indicators
from strategy import evaluate_candle
from risk_manager import RiskManager

ACTIVE_TRADES_FILE = os.path.join(os.path.dirname(__file__), "active_trades.json")

def load_active_trades():
    if os.path.exists(ACTIVE_TRADES_FILE):
        try:
            with open(ACTIVE_TRADES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_active_trades(trades):
    with open(ACTIVE_TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

class ConfluenceTradingBot:
    def __init__(self):
        self.client = BinanceClient()
        self.risk_manager = RiskManager()
        self.active_trades = load_active_trades()
        print("=" * 80)
        print("🚀 ULTRA TRADING BOT - ENGINE 3: 10-POINT CONFLUENCE SCALPER")
        print(f"Timeframe: {TIMEFRAME} | Max Risk/Trade: 1% | Leverage: {LEVERAGE}x Isolated")
        print(f"Mode: {'[DRY RUN / PAPER TRADING]' if DRY_RUN else '[LIVE FUTURES TRADING]'}")
        print(f"Monitoring {len(SYMBOLS)} Top Crypto USDT Pairs")
        print("=" * 80)

    def manage_open_positions(self):
        closed_symbols = []
        for symbol, pos in list(self.active_trades.items()):
            candles = self.client.fetch_klines(symbol, interval=TIMEFRAME, limit=10)
            if not candles:
                continue

            last_c = candles[-1]
            current_price = last_c['close']
            pos_type = pos['type']
            entry_price = pos['entry_price']
            sl_price = pos['sl_price']
            tp_price = pos['tp_price']
            bars_held = pos.get('bars_held', 0) + 1
            pos['bars_held'] = bars_held

            exit_reason = None
            if pos_type == "LONG":
                if last_c['high'] >= tp_price:
                    exit_reason = "TP_HIT"
                elif last_c['low'] <= sl_price:
                    exit_reason = "SL_HIT"
                elif bars_held >= MAX_HOLD_CANDLES:
                    exit_reason = "MAX_HOLD_TIMEOUT"
            elif pos_type == "SHORT":
                if last_c['low'] <= tp_price:
                    exit_reason = "TP_HIT"
                elif last_c['high'] >= sl_price:
                    exit_reason = "SL_HIT"
                elif bars_held >= MAX_HOLD_CANDLES:
                    exit_reason = "MAX_HOLD_TIMEOUT"

            if exit_reason:
                pnl_pct = ((current_price - entry_price) / entry_price * 100) if pos_type == "LONG" else ((entry_price - current_price) / entry_price * 100)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🏁 Position Closed: {symbol} ({pos_type}) | Reason: {exit_reason} | Return: {pnl_pct:+.2f}%")
                closed_symbols.append(symbol)

        for sym in closed_symbols:
            del self.active_trades[sym]
        if closed_symbols:
            save_active_trades(self.active_trades)

    def scan_for_signals(self):
        equity = self.client.get_account_balance()
        for symbol in SYMBOLS:
            if symbol in self.active_trades:
                continue

            candles = self.client.fetch_klines(symbol, interval=TIMEFRAME, limit=150)
            if not candles or len(candles) < 60:
                continue

            data = calc_all_indicators(candles, timeframe=TIMEFRAME)
            if not data:
                continue

            eval_res = evaluate_candle(data, len(candles) - 1)
            signal = eval_res['signal']
            score = eval_res['long_score'] if signal == "LONG" else eval_res['short_score']

            if signal:
                entry_price = eval_res['entry_price']
                sl_price = eval_res['sl_price']
                tp_price = eval_res['tp_price']

                notional, qty = self.risk_manager.calculate_position_size(equity, entry_price, sl_price)
                can_trade, reason = self.risk_manager.can_open_trade(len(self.active_trades), equity, notional / LEVERAGE)

                if not can_trade:
                    print(f"[{symbol}] Signal {signal} (Score {score:.1f}/10) skipped: {reason}")
                    continue

                print("\n" + "#" * 60)
                print(f"🚨 CONFLUENCE SIGNAL TRIGGERED: {symbol} {signal}!")
                print(f"Score: {score:.1f}/10 | Entry: {entry_price:.4f} | SL: {sl_price:.4f} | TP: {tp_price:.4f}")
                print(f"Position: ${notional:.2f} (1.0% Risk Capped) | Qty: {qty} | Lev: {LEVERAGE}x")
                print("#" * 60 + "\n")

                # Set leverage and execute
                self.client.set_leverage(symbol, LEVERAGE)
                order = self.client.place_market_order(symbol, "BUY" if signal == "LONG" else "SELL", qty)
                if order:
                    self.client.place_sl_tp_orders(symbol, signal, qty, sl_price, tp_price)
                    self.active_trades[symbol] = {
                        'symbol': symbol,
                        'type': signal,
                        'entry_price': entry_price,
                        'sl_price': sl_price,
                        'tp_price': tp_price,
                        'notional': notional,
                        'qty': qty,
                        'bars_held': 0,
                        'timestamp': int(time.time() * 1000)
                    }
                    save_active_trades(self.active_trades)

    def run(self):
        while True:
            try:
                self.manage_open_positions()
                self.scan_for_signals()
            except Exception as e:
                print(f"[Engine 3 Error] {e}")

            time.sleep(30)  # Scan every 30 seconds

if __name__ == "__main__":
    bot = ConfluenceTradingBot()
    bot.run()
