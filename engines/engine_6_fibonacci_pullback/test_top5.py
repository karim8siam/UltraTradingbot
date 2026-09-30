import urllib.request, json, time
from backtest.dataset import HistoricalDataset
from backtest.engine import BacktestEngine
from core.types import Candle

def fetch_klines(symbol, interval, limit=1000):
    url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    return [Candle(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5]), int(x[6])) for x in raw]

for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "AVAXUSDT"]:
    c_5m = fetch_klines(sym, "5m", 1000)
    c_15m = fetch_klines(sym, "15m", 1000)
    c_1h = fetch_klines(sym, "1h", 500)
    c_4h = fetch_klines(sym, "4h", 300)
    
    ds = HistoricalDataset(sym)
    ds.candles_5m = c_5m
    ds.candles_15m = c_15m
    ds.candles_1h = c_1h
    ds.candles_4h = c_4h
    
    engine = BacktestEngine(initial_capital=10000.0)
    engine.risk_manager.trading_sessions = [(0, 0, 23, 59)]
    metrics = engine.run(ds)
    pnl_str = format(metrics.net_pnl, "+,.2f")
    print(f"{sym}: {len(engine.closed_trades)} trades | WinRate: {metrics.win_rate*100:.1f}% | Net PnL: $" + pnl_str)
