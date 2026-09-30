import datetime
import builtins
import functools
print = functools.partial(builtins.print, flush=True)

import json
import urllib.request
import ssl
import config
from strategy import Momentum3CandleStrategy

ctx = ssl.create_default_context()

def get_klines_quick(symbol):
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=15m&limit=6"
        req = urllib.request.Request(url, headers={"User-Agent": "Bot/1.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            klines = []
            for k in data:
                klines.append({
                    "open_time": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                })
            return klines
    except Exception as e:
        return []

print("\n" + "=" * 90)
print(f"  LIVE 15M MARKET SCAN REPORT — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 90)

for sym in config.SYMBOLS:
    klines = get_klines_quick(sym)
    if len(klines) < 5:
        print(f"{sym:<10} | Could not fetch klines")
        continue

    c_prev, c1, c2, c3, c_live = klines[-5], klines[-4], klines[-3], klines[-2], klines[-1]

    def fmt_c(c):
        color = "🟢 GREEN" if c["close"] > c["open"] else ("🔴 RED" if c["close"] < c["open"] else "⚪ FLAT")
        rng = c["high"] - c["low"]
        body = abs(c["close"] - c["open"])
        bp = (body / rng * 100) if rng > 0 else 0
        h = "Healthy" if bp >= 50 else "Doji/Weak"
        return f"{color} ({bp:.0f}% Body - {h})"

    signal = Momentum3CandleStrategy.evaluate_klines(klines)

    # Breakdown reason
    colors = ["GREEN" if c["close"] > c["open"] else "RED" for c in [c1, c2, c3]]
    prev_color = "GREEN" if c_prev["close"] > c_prev["open"] else "RED"

    print(f"\n🪙 {sym}:")
    print(f"   Candle 0 (05:45): {fmt_c(c_prev)}")
    print(f"   Candle 1 (06:00): {fmt_c(c1)}")
    print(f"   Candle 2 (06:15): {fmt_c(c2)}")
    print(f"   Candle 3 (06:30): {fmt_c(c3)}")
    print(f"   Live (06:45-07:00): In progress...")

    if signal:
        print(f"   👉 RESULT: 🎯 VALID SIGNAL DETECTED: {signal}!")
    else:
        if len(set(colors)) > 1:
            print(f"   👉 RESULT: ❌ NO TRADE -> Mixed colors ({', '.join(colors)}). Strategy requires 3 back-to-back same color.")
        elif prev_color == colors[0]:
            print(f"   👉 RESULT: ❌ NO TRADE -> Preceding candle (C0) was also {colors[0]}. Violates 'fresh 3-candle rule' (this is candle 4+).")
        else:
            print(f"   👉 RESULT: ❌ NO TRADE -> Failed healthy candle filter (one or more candles was a Doji / small body <50% range).")

print("\n" + "=" * 90)
