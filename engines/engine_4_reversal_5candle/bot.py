import time
import datetime
import os
import json
from typing import Dict, Any
import config
from binance_client import BinanceFuturesClient
from strategy import Momentum3CandleStrategy
from risk_manager import RiskManager

import builtins
import functools
print = functools.partial(builtins.print, flush=True)

class BinanceMomentumBot:
    def __init__(self):
        self.client = BinanceFuturesClient()
        self.risk_manager = RiskManager(self.client)
        self.tracked_trades: Dict[str, Dict[str, Any]] = {}
        self.last_candle_time: Dict[str, int] = {}
        self.state_file = os.path.join(os.path.dirname(__file__), "active_trades.json")
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    self.tracked_trades = json.load(f)
                print(f"[INIT] Loaded {len(self.tracked_trades)} active trades from state file.")
            except Exception as e:
                print(f"[WARN] Could not load state file: {e}")

    def _save_state(self):
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.tracked_trades, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Could not save state file: {e}")

    def setup(self):
        print("=" * 60)
        print("  BINANCE FUTURES 15M 5-CANDLE REVERSAL BOT")
        print("=" * 60)
        print(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Dry Run Mode: {config.DRY_RUN}")
        print(f"Target Timeframe: {config.TIMEFRAME}")
        print(f"Leverage: {config.LEVERAGE}x")
        print(f"Margin per Trade: {config.MARGIN_FRACTION * 100}%")
        print(f"Max Concurrent Trades: {config.MAX_CONCURRENT_TRADES}")
        print(f"Hold Duration: {config.HOLD_MINUTES} minutes (3 candles)")
        print(f"Symbols ({len(config.SYMBOLS)}): {', '.join(config.SYMBOLS)}")
        print("=" * 60)

        # Check server time & balance
        srv_time = self.client.get_server_time()
        if not srv_time:
            print("[WARN] Could not connect to Binance API. Check network/IP permissions.")
        else:
            print("[OK] Connected to Binance Futures successfully.")

        balance = self.client.get_usdt_balance()
        print(f"[BALANCE] Total Futures Wallet Balance: ${balance:.2f} USDT")

        # Configure leverage & isolated margin for all pairs, and initialize candle baseline
        if not config.DRY_RUN:
            print("[SETUP] Configuring 5x leverage & ISOLATED margin mode...")
            for symbol in config.SYMBOLS:
                self.client.set_margin_type(symbol, "ISOLATED")
                self.client.set_leverage(symbol, config.LEVERAGE)
                time.sleep(0.05)

        # Baseline candle timestamps on startup so bot only trades on live future closes
        print("[SETUP] Setting candle close baseline for all pairs...")
        for symbol in config.SYMBOLS:
            klines = self.client.get_klines(symbol, interval=config.TIMEFRAME, limit=3)
            if len(klines) >= 2:
                self.last_candle_time[symbol] = klines[-2]["open_time"]
            time.sleep(0.05)

    def check_exits(self):
        """
        Check all active trades and close positions that reached 30 minutes.
        """
        now = time.time()
        active_symbols = list(self.tracked_trades.keys())

        for symbol in active_symbols:
            trade = self.tracked_trades[symbol]
            entry_time = trade["entry_time"]
            elapsed_minutes = (now - entry_time) / 60.0

            if elapsed_minutes >= config.HOLD_MINUTES:
                print(f"\n[TIME-EXIT] Closing trade on {symbol} - Reached {elapsed_minutes:.1f} mins (Target: {config.HOLD_MINUTES}m)")
                side_to_close = "SELL" if trade["side"] == "BUY" else "BUY"
                qty = trade["quantity"]

                if config.DRY_RUN:
                    curr_price = self.client.get_current_price(symbol)
                    pnl_pct = ((curr_price - trade['entry_price']) / trade['entry_price'] * 100) if trade["side"] == "BUY" else ((trade['entry_price'] - curr_price) / trade['entry_price'] * 100)
                    print(f"[SIMULATED EXIT] {symbol} {side_to_close} Qty: {qty} | Entry: {trade['entry_price']} -> Exit: {curr_price} | ROI: {pnl_pct * config.LEVERAGE:.2f}%")
                    del self.tracked_trades[symbol]
                    self._save_state()
                else:
                    res = self.client.close_market_position(symbol, side_to_close, qty)
                    if res and ("orderId" in res or res.get("status") in ["NEW", "FILLED", "PARTIALLY_FILLED"]):
                        print(f"[LIVE EXIT SUCCESS] {symbol} Position closed: {res.get('orderId')}")
                        del self.tracked_trades[symbol]
                        self._save_state()
                    else:
                        print(f"[LIVE EXIT ERROR] {symbol} Close failed ({res}). Will retry in next loop...")

    def scan_and_trade(self):
        """
        Scan top 10 pairs on new 15m candle close and execute valid signals.
        """
        # Fetch current open positions from exchange
        real_positions = self.client.get_active_positions() if not config.DRY_RUN else []
        active_count = len(self.tracked_trades)

        for symbol in config.SYMBOLS:
            # Fetch latest 15m klines
            klines = self.client.get_klines(symbol, interval=config.TIMEFRAME, limit=8)
            if len(klines) < 5:
                continue

            latest_closed_candle = klines[-2]
            closed_time = latest_closed_candle["open_time"]

            # Only evaluate when a new candle has completed
            if self.last_candle_time.get(symbol) == closed_time:
                continue

            self.last_candle_time[symbol] = closed_time
            signal = Momentum3CandleStrategy.evaluate_klines(klines)

            if signal:
                readable_time = datetime.datetime.fromtimestamp(closed_time / 1000).strftime('%H:%M')
                print(f"\n[SIGNAL DETECTED] {symbol} | Signal: {signal} | Candle Closed: {readable_time}")

                # Check concurrency limits
                if not self.risk_manager.can_open_new_trade(symbol, real_positions if not config.DRY_RUN else list(self.tracked_trades.values())):
                    continue

                if active_count >= config.MAX_CONCURRENT_TRADES:
                    print(f"[RISK] Max concurrent trades reached ({active_count}/{config.MAX_CONCURRENT_TRADES}). Skipping signal.")
                    continue

                # Calculate position size
                balance = self.client.get_usdt_balance()
                current_price = self.client.get_current_price(symbol)
                qty = self.risk_manager.calculate_order_quantity(symbol, current_price, balance)

                if not qty or qty <= 0:
                    print(f"[RISK] Calculated quantity for {symbol} is 0. Skipping.")
                    continue

                print(f"[ENTRY] Placing {signal} on {symbol} | Price: {current_price} | Qty: {qty} | Margin: ${(balance * config.MARGIN_FRACTION):.2f} (5x Lev)")

                if config.DRY_RUN:
                    self.tracked_trades[symbol] = {
                        "symbol": symbol,
                        "side": signal,
                        "quantity": qty,
                        "entry_price": current_price,
                        "entry_time": time.time(),
                    }
                    self._save_state()
                    active_count += 1
                else:
                    order = self.client.place_market_order(symbol, signal, qty)
                    if order and "orderId" in order:
                        print(f"[ORDER PLACED] Order ID: {order['orderId']}")
                        self.tracked_trades[symbol] = {
                            "symbol": symbol,
                            "side": signal,
                            "quantity": qty,
                            "entry_price": current_price,
                            "entry_time": time.time(),
                        }
                        self._save_state()
                        active_count += 1
                    else:
                        print(f"[ORDER FAILED] Could not enter trade for {symbol}.")

    def run(self):
        self.setup()
        print("\n[BOT RUNNING] Monitoring 15m candles and managing active 30-minute positions...\n")
        last_heartbeat = 0

        try:
            while True:
                now = time.time()
                # Periodic heartbeat log every 3 minutes
                if now - last_heartbeat > 180:
                    balance = self.client.get_usdt_balance()
                    dt_str = datetime.datetime.now().strftime('%H:%M:%S')
                    print(f"[{dt_str}] [HEARTBEAT] Bot active & scanning {len(config.SYMBOLS)} pairs | Balance: ${balance:.2f} USDT | Open Trades: {len(self.tracked_trades)}/{config.MAX_CONCURRENT_TRADES}")
                    last_heartbeat = now

                # 1. Manage time-based exits
                self.check_exits()

                # 2. Scan pairs for signals
                self.scan_and_trade()

                # 3. Sleep before next check
                time.sleep(10)

        except KeyboardInterrupt:
            print("\n[STOP] Bot stopped gracefully by user.")
            self._save_state()

if __name__ == "__main__":
    bot = BinanceMomentumBot()
    bot.run()
