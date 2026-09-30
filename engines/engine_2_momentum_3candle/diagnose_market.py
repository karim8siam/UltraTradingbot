import datetime
import builtins
import functools
print = functools.partial(builtins.print, flush=True)

import config
from binance_client import BinanceFuturesClient
from strategy import Momentum3CandleStrategy

def diagnose():
    client = BinanceFuturesClient()
    print("=" * 95)
    print(f"  LIVE 15M CANDLE DIAGNOSTIC SCAN ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 95)

    for symbol in config.SYMBOLS:
        klines = client.get_klines(symbol, interval="15m", limit=7)
        if len(klines) < 5:
            print(f"[{symbol}] Not enough kline data.")
            continue

        c_prev = klines[-5]  # e.g. 06:45
        c1 = klines[-4]      # e.g. 07:00
        c2 = klines[-3]      # e.g. 07:15
        c3 = klines[-2]      # e.g. 07:30 (most recently closed)
        c_live = klines[-1]  # 07:45 live

        def fmt_c(c):
            is_green = c["close"] > c["open"]
            is_red = c["close"] < c["open"]
            color = "🟢 GREEN" if is_green else ("🔴 RED" if is_red else "⚪ FLAT")
            doji = Momentum3CandleStrategy.is_doji(c)
            doji_str = " (DOJI)" if doji else ""
            t_str = datetime.datetime.fromtimestamp(c["open_time"] / 1000).strftime('%H:%M')
            return f"[{t_str}] {color}{doji_str} (O: {c['open']}, C: {c['close']})"

        signal = Momentum3CandleStrategy.evaluate_klines(klines)

        colors = ["GREEN" if c["close"] > c["open"] else ("RED" if c["close"] < c["open"] else "FLAT") for c in [c1, c2, c3]]
        prev_color = "GREEN" if c_prev["close"] > c_prev["open"] else ("RED" if c_prev["close"] < c_prev["open"] else "FLAT")

        print(f"\n🪙 {symbol}:")
        print(f"   C0 (Prior) : {fmt_c(c_prev)}")
        print(f"   C1 (1st)   : {fmt_c(c1)}")
        print(f"   C2 (2nd)   : {fmt_c(c2)}")
        print(f"   C3 (3rd)   : {fmt_c(c3)}")
        print(f"   Live candle: Open at {datetime.datetime.fromtimestamp(c_live['open_time'] / 1000).strftime('%H:%M')}")

        if signal:
            print(f"   👉 RESULT: 🎯 VALID SIGNAL DETECTED -> {signal}!")
        else:
            reasons = []
            if len(set(colors)) > 1 or "FLAT" in colors:
                reasons.append(f"Mixed colors ({', '.join(colors)}) — requires 3 back-to-back same color")
            else:
                same_color = colors[0]
                if prev_color == same_color:
                    reasons.append(f"Preceding candle C0 was already {same_color} (Violates fresh start; this is candle 4+)")
                dojis = []
                if Momentum3CandleStrategy.is_doji(c1): dojis.append("C1")
                if Momentum3CandleStrategy.is_doji(c2): dojis.append("C2")
                if Momentum3CandleStrategy.is_doji(c3): dojis.append("C3")
                if dojis:
                    reasons.append(f"Contains Doji candle ({', '.join(dojis)})")
            
            print(f"   👉 RESULT: ❌ NO TRADE -> {'; '.join(reasons)}")

    print("\n" + "=" * 95)

if __name__ == "__main__":
    diagnose()
