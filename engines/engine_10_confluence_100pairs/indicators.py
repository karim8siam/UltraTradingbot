import numpy as np
import pandas as pd

def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=1).mean()

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_adx_dmi(df: pd.DataFrame, period: int = 14):
    high = df["high"]
    low = df["low"]
    close = df["close"]
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    tr_smooth = pd.Series(tr, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    
    plus_di = 100 * (plus_dm_smooth / (tr_smooth + 1e-10))
    minus_di = 100 * (minus_dm_smooth / (tr_smooth + 1e-10))
    
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx, plus_di, minus_di

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    tp_vol = typical_price * df["volume"]
    window = min(len(df), 100)
    cum_vol = df["volume"].rolling(window=window, min_periods=1).sum()
    cum_tp_vol = tp_vol.rolling(window=window, min_periods=1).sum()
    vwap = cum_tp_vol / (cum_vol + 1e-10)
    return vwap

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def compute_all_indicators(df_primary: pd.DataFrame, df_macro: pd.DataFrame, book_ticker: dict = None) -> dict:
    """Computes all technical indicators for the 0.55x ATR Scalper Engines."""
    if df_primary is None or len(df_primary) < 30:
        return {}
    
    close = df_primary["close"]
    high = df_primary["high"]
    low = df_primary["low"]
    volume = df_primary["volume"]
    
    # 1. EMA Ribbon: 9, 21, 50
    ema9 = calculate_ema(close, 9)
    ema21 = calculate_ema(close, 21)
    ema50 = calculate_ema(close, 50)
    
    # 2. ATR & ATR_SMA(20)
    atr = calculate_atr(df_primary, 14)
    atr_sma20 = calculate_sma(atr, 20)
    
    # 3. ADX, +DI, -DI
    adx, plus_di, minus_di = calculate_adx_dmi(df_primary, 14)
    
    # 4. VWAP
    vwap = calculate_vwap(df_primary)
    
    # 5. RVOL (20 period)
    vol_sma20 = calculate_sma(volume, 20)
    rvol = volume / (vol_sma20 + 1e-10)
    
    # 6. MACD (12, 26, 9)
    macd_line, signal_line, macd_hist = calculate_macd(close, 12, 26, 9)
    
    # 7. RSI (14)
    rsi = calculate_rsi(close, 14)
    
    # 8. 1H Macro EMA 200
    macro_ema200 = None
    if df_macro is not None and len(df_macro) >= 20:
        macro_ema200 = calculate_ema(df_macro["close"], min(len(df_macro), 200)).iloc[-1]
        
    # 9. Orderbook Spread
    spread = 0.0001
    if book_ticker and float(book_ticker.get("bidPrice", 0)) > 0:
        bid = float(book_ticker["bidPrice"])
        ask = float(book_ticker["askPrice"])
        spread = (ask - bid) / bid
        
    return {
        "close": close.iloc[-1],
        "prev_close": close.iloc[-2],
        "open": df_primary["open"].iloc[-1],
        "prev_open": df_primary["open"].iloc[-2],
        "high": high.iloc[-1],
        "low": low.iloc[-1],
        "volume": volume.iloc[-1],
        "ema9": ema9.iloc[-1],
        "ema21": ema21.iloc[-1],
        "ema50": ema50.iloc[-1],
        "macro_ema200": macro_ema200,
        "atr": atr.iloc[-1],
        "atr_sma20": atr_sma20.iloc[-1],
        "adx": adx.iloc[-1],
        "plus_di": plus_di.iloc[-1],
        "minus_di": minus_di.iloc[-1],
        "vwap": vwap.iloc[-1],
        "rvol": rvol.iloc[-1],
        "macd_line": macd_line.iloc[-1],
        "signal_line": signal_line.iloc[-1],
        "macd_hist": macd_hist.iloc[-1],
        "prev_macd_hist": macd_hist.iloc[-2],
        "rsi": rsi.iloc[-1],
        "spread": spread
    }
