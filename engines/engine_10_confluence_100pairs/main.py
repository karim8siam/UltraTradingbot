import os
import sys
import time
import datetime
from concurrent.futures import ThreadPoolExecutor
from colorama import Fore, Back, Style, init
from tabulate import tabulate

import config
from indicators import compute_all_indicators
from engine import LongEngine, ShortEngine
from binance_client import BinanceFuturesClient

init(autoreset=True)

def print_header(balance: float, active_trades_count: int):
    os.system("cls" if os.name == "nt" else "clear")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(Fore.CYAN + Style.BRIGHT + "=" * 85)
    print(Fore.YELLOW + Style.BRIGHT + f" 🤖 BINANCE FUTURES DUAL-ENGINE 10-POINT BOT  |  {now}")
    print(Fore.CYAN + Style.BRIGHT + "=" * 85)
    print(Fore.WHITE + f" 💰 Futures Balance: {Fore.GREEN}{balance:.2f} USDT"
          f"{Fore.WHITE} | ⚙️ Leverage: {Fore.MAGENTA}{config.LEVERAGE}x"
          f"{Fore.WHITE} | 📊 Risk: {Fore.CYAN}{config.RISK_PERCENT*100:.1f}%"
          f"{Fore.WHITE} | 🎯 Target Score: {Fore.YELLOW}>={config.SCORE_TRIGGER}/10"
          f"{Fore.WHITE} | 🛡️ Active: {Fore.YELLOW}{active_trades_count}/{config.MAX_OPEN_POSITIONS}")
    print(Fore.CYAN + "-" * 85)

def format_score(score: int) -> str:
    if score >= 7:
        return Fore.GREEN + Style.BRIGHT + f"{score}/10 [TRIGGER]"
    elif score >= 5:
        return Fore.YELLOW + f"{score}/10"
    else:
        return Fore.WHITE + f"{score}/10"

def evaluate_symbol(client: BinanceFuturesClient, symbol: str, active_symbols: set):
    display_name = symbol.replace("USDT", "")
    
    if symbol in active_symbols:
        return {
            "symbol": symbol,
            "row": [display_name, "IN POSITION", "-", "-", "-", "Position Locked"],
            "action": None
        }
        
    df_5m = client.fetch_klines(symbol, timeframe=config.TIMEFRAME_PRIMARY, limit=80)
    df_1h = client.fetch_klines(symbol, timeframe=config.TIMEFRAME_MACRO, limit=150)
    
    ind = compute_all_indicators(df_5m, df_1h)
    if not ind:
        return {
            "symbol": symbol,
            "row": [display_name, "DATA ERROR", "-", "-", "-", "Syncing"],
            "action": None
        }
        
    long_res = LongEngine.evaluate(ind, sl_mult=config.SL_ATR_MULT, tp_mult=config.TP_ATR_MULT)
    short_res = ShortEngine.evaluate(ind, sl_mult=config.SL_ATR_MULT, tp_mult=config.TP_ATR_MULT)
    
    price_val = ind["close"]
    price_str = f"{price_val:.4f}" if price_val < 10 else f"{price_val:.2f}"
    status_str = Fore.LIGHTBLACK_EX + "Watching"
    action = None
    
    if long_res.should_trade:
        status_str = Fore.GREEN + Style.BRIGHT + "🔥 LONG SIGNAL"
        action = ("LONG", long_res, ind)
    elif short_res.should_trade:
        status_str = Fore.RED + Style.BRIGHT + "🔥 SHORT SIGNAL"
        action = ("SHORT", short_res, ind)
        
    rsi_val = ind["rsi"]
    row = [
        display_name,
        price_str,
        format_score(long_res.score),
        format_score(short_res.score),
        f"{rsi_val:.1f}",
        status_str
    ]
    
    return {
        "symbol": symbol,
        "row": row,
        "action": action
    }

def run_bot():
    print(Fore.CYAN + "[*] Starting Binance Futures Trading Bot...")
    client = BinanceFuturesClient()
    
    while True:
        try:
            # 1. Fetch balance and active positions
            balance = client.get_usdt_balance()
            active_positions = client.get_open_positions()
            active_symbols = set(active_positions.keys())
            
            print_header(balance, len(active_symbols))
            
            # Display active positions if any
            if active_positions:
                pos_table = []
                for sym, pos in active_positions.items():
                    side_color = Fore.GREEN if pos["side"] == "LONG" else Fore.RED
                    pnl_color = Fore.GREEN if pos["unrealized_pnl"] >= 0 else Fore.RED
                    contracts = pos["contracts"]
                    entry_p = pos["entry_price"]
                    pnl = pos["unrealized_pnl"]
                    pct = pos["percentage"]
                    pos_table.append([
                        sym.replace("USDT", ""),
                        side_color + pos["side"],
                        str(contracts),
                        f"{entry_p:.4f}",
                        pnl_color + f"{pnl:.2f} USDT ({pct:.2f}%)"
                    ])
                print(Fore.WHITE + Style.BRIGHT + " [📍 ACTIVE POSITIONS]")
                print(tabulate(pos_table, headers=["Symbol", "Side", "Qty", "Entry Price", "Unrealized PnL"], tablefmt="simple"))
                print(Fore.CYAN + "-" * 85)

            # 2. Parallel Fast Scanner across Top 20 Pairs
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(evaluate_symbol, client, sym, active_symbols) for sym in config.SYMBOLS]
                results = [f.result() for f in futures]
                
            scan_rows = []
            for res in results:
                scan_rows.append(res["row"])
                
                # Check if signal triggered trade
                if res["action"] and len(active_symbols) < config.MAX_OPEN_POSITIONS:
                    side, engine_res, ind = res["action"]
                    sym = res["symbol"]
                    if sym not in active_symbols:
                        amount = client.calculate_order_amount(sym, ind["close"], balance)
                        print(Fore.MAGENTA + f"\n🚀 [{side} TRIGGER] {sym} | Score: {engine_res.score}/10 | Rules: {engine_res.passed_rules}")
                        client.place_market_entry_with_sl_tp(
                            symbol=sym,
                            side=side,
                            amount=amount,
                            entry_price=engine_res.entry_price,
                            sl_price=engine_res.stop_loss,
                            tp_price=engine_res.take_profit
                        )
                        active_symbols.add(sym)

            # 3. Print Scanner Table
            print(Fore.WHITE + Style.BRIGHT + " [📡 LIVE 10-POINT MARKET SCANNER (5m / 1h Macro)]")
            headers = ["Symbol", "Price", "🟢 Long Score", "🔴 Short Score", "RSI (14)", "Status"]
            print(tabulate(scan_rows, headers=headers, tablefmt="grid"))
            print(Fore.CYAN + f"\n[⏳] Next scan cycle in {config.SCAN_INTERVAL} seconds... (Press Ctrl+C to stop)")
            
            time.sleep(config.SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\n[!] Bot stopped safely by user.")
            sys.exit(0)
        except Exception as e:
            print(Fore.RED + f"\n[!] Scanner error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_bot()
