import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import SYMBOLS, TIMEFRAME, MIN_SCORE
from binance_client import BinanceClient
from indicators import calc_all_indicators
from strategy import evaluate_candle

def scan_symbol(client, symbol):
    candles = client.fetch_klines(symbol, interval=TIMEFRAME, limit=120)
    if not candles or len(candles) < 50:
        return None
    data = calc_all_indicators(candles, timeframe=TIMEFRAME)
    if not data:
        return None
    res = evaluate_candle(data, len(candles) - 1)
    res['symbol'] = symbol
    return res

def main():
    print("=" * 80)
    print(f"🔍 SCANNING TOP {len(SYMBOLS)} CRYPTO PAIRS ({TIMEFRAME} Timeframe)")
    print(f"Target Confluence Threshold: >= {MIN_SCORE} / 10 Points")
    print("=" * 80)

    client = BinanceClient()
    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(scan_symbol, client, sym): sym for sym in SYMBOLS}
        for f in as_completed(futs):
            r = f.result()
            if r:
                results.append(r)

    results.sort(key=lambda x: max(x['long_score'], x['short_score']), reverse=True)

    print(f"{'SYMBOL':<10} | {'LONG SCORE':<12} | {'SHORT SCORE':<12} | {'SIGNAL':<8} | {'PRICE':<12}")
    print("-" * 65)

    triggered = []
    for r in results:
        l_s = r['long_score']
        s_s = r['short_score']
        sig = r['signal'] or "WAIT"
        price = r['entry_price']
        print(f"{r['symbol']:<10} | {l_s:4.1f} / 10    | {s_s:4.1f} / 10    | {sig:<8} | ${price:<11.4f}")
        if r['signal']:
            triggered.append(r)

    print("=" * 80)
    if triggered:
        print(f"🚨 {len(triggered)} ACTIVE ACTIONABLE CONFLUENCE SIGNALS DETECTED:")
        for t in triggered:
            print(f"  👉 {t['symbol']} {t['signal']} (Score {t['long_score'] if t['signal']=='LONG' else t['short_score']:.1f}/10) | TP: {t['tp_price']:.4f} | SL: {t['sl_price']:.4f}")
    else:
        print("✅ Market scanned. No pair currently meets the >= 8.0/10 execution threshold.")
    print("=" * 80)

if __name__ == "__main__":
    main()
