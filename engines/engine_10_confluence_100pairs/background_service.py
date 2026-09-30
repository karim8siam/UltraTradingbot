import os
import sys
import time
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

import config
from indicators import compute_all_indicators
from engine import LongEngine, ShortEngine
from binance_client import BinanceFuturesClient

log_file = "/Users/karimsiam/.gemini/antigravity/scratch/binance_futures_bot/bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
    ]
)

def evaluate_symbol(client: BinanceFuturesClient, symbol: str, active_symbols: set):
    if symbol in active_symbols:
        return {"symbol": symbol, "status": "IN_POSITION", "action": None}
        
    df_5m = client.fetch_klines(symbol, timeframe=config.TIMEFRAME_PRIMARY, limit=80)
    df_1h = client.fetch_klines(symbol, timeframe=config.TIMEFRAME_MACRO, limit=150)
    book_ticker = client.fetch_book_ticker(symbol)
    
    ind = compute_all_indicators(df_5m, df_1h, book_ticker)
    if not ind:
        return {"symbol": symbol, "status": "NO_DATA", "action": None}
        
    long_res = LongEngine.evaluate(ind, sl_mult=config.SL_ATR_MULT, tp_mult=config.TP_ATR_MULT, threshold=config.SCORE_TRIGGER)
    short_res = ShortEngine.evaluate(ind, sl_mult=config.SL_ATR_MULT, tp_mult=config.TP_ATR_MULT, threshold=config.SCORE_TRIGGER)
    
    action = None
    if long_res.should_trade:
        action = ("LONG", long_res, ind)
    elif short_res.should_trade:
        action = ("SHORT", short_res, ind)
        
    return {
        "symbol": symbol,
        "price": ind["close"],
        "long_score": long_res.score,
        "short_score": short_res.score,
        "rsi": ind["rsi"],
        "adx": ind["adx"],
        "action": action
    }

def run_background_bot():
    logging.info("==========================================================")
    logging.info("🚀 Binance Futures 0.60x ATR Scalper (Strict 10.0/10.0 Confluence)")
    logging.info(f"⚙️ Config: Leverage={config.LEVERAGE}x | Risk={config.RISK_PERCENT*100}% | Trigger=10/10 | SL/TP=0.60x ATR")
    logging.info("==========================================================")
    
    client = BinanceFuturesClient()
    cycle = 0
    
    while True:
        try:
            cycle += 1
            balance = client.get_usdt_balance()
            active_positions = client.get_open_positions()
            active_symbols = set(active_positions.keys())
            
            # Parallel Evaluation across 100 pairs
            with ThreadPoolExecutor(max_workers=16) as executor:
                futures = [executor.submit(evaluate_symbol, client, sym, active_symbols) for sym in config.SYMBOLS]
                results = [f.result() for f in futures]
                
            high_interest = []
            for res in results:
                sym = res["symbol"]
                if res.get("action") and len(active_symbols) < config.MAX_OPEN_POSITIONS:
                    side, engine_res, ind = res["action"]
                    if sym not in active_symbols:
                        amount = client.calculate_order_amount(sym, ind["close"], balance)
                        logging.info(f"🔥 [{side} SCALPER TRIGGER] {sym} | Score: {engine_res.score:.1f}/10.0 (Passed: {engine_res.passed_rules})")
                        order = client.place_market_entry_with_sl_tp(
                            symbol=sym,
                            side=side,
                            amount=amount,
                            entry_price=engine_res.entry_price,
                            sl_price=engine_res.stop_loss,
                            tp_price=engine_res.take_profit
                        )
                        if order:
                            active_symbols.add(sym)
                            position_entry_timestamps[sym] = now
                
                ls = res.get("long_score", 0)
                ss = res.get("short_score", 0)
                if ls >= 5 or ss >= 5:
                    high_interest.append(f"{sym}: L={ls:.0f}/10 S={ss:.0f}/10")

            # Periodic log every 3 cycles
            if cycle % 3 == 0:
                pos_list = []
                for s, p in active_positions.items():
                    side_str = p.get("side", "")
                    pnl_val = p.get("unrealized_pnl", 0.0)
                    pos_list.append(f"{s}({side_str} PnL:{pnl_val:.2f})")
                pos_summary = ", ".join(pos_list) if pos_list else "None"
                notable = ", ".join(high_interest) if high_interest else "None"
                logging.info(f"[Cycle {cycle}] Balance: {balance:.2f} USDT | Active: {len(active_symbols)}/{config.MAX_OPEN_POSITIONS} ({pos_summary}) | Notable: {notable}")
                
            time.sleep(config.SCAN_INTERVAL)
            
        except Exception as e:
            logging.error(f"Error in scan loop: {e}", exc_info=True)
            time.sleep(5)

if __name__ == "__main__":
    run_background_bot()
