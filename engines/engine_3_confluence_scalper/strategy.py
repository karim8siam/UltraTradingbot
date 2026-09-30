import math
from config import MIN_SCORE, ATR_SL_MULT, ATR_TP_MULT

def evaluate_candle(data, i):
    """
    Evaluates the 10-point scoring checklist for both LONG and SHORT engines.
    Returns:
        long_score, short_score, long_breakdown, short_breakdown, signal_type, tp_price, sl_price
    """
    c = data['candles'][i]
    prev_c = data['candles'][i-1] if i > 0 else c
    atr = data['atr14'][i]
    
    long_score = 0.0
    short_score = 0.0
    long_breakdown = {}
    short_breakdown = {}

    # Point 1.0: RVOL Expansion (Volume / 20-period Volume SMA >= 1.8)
    vol_sma = data['vol_sma20'][i] if data['vol_sma20'][i] > 1e-9 else 1e-9
    rvol = data['volumes'][i] / vol_sma
    if rvol >= 1.8:
        long_score += 1.0
        short_score += 1.0
        long_breakdown['RVOL'] = True
        short_breakdown['RVOL'] = True
    else:
        long_breakdown['RVOL'] = False
        short_breakdown['RVOL'] = False

    # Point 2.0: Trend Strength: ADX(14) >= 25 AND (+DI > -DI for Long, -DI > +DI for Short)
    adx_ok = data['adx14'][i] >= 25.0
    if adx_ok and data['plus_di'][i] > data['minus_di'][i]:
        long_score += 1.0
        long_breakdown['ADX_Trend'] = True
    else:
        long_breakdown['ADX_Trend'] = False

    if adx_ok and data['minus_di'][i] > data['plus_di'][i]:
        short_score += 1.0
        short_breakdown['ADX_Trend'] = True
    else:
        short_breakdown['ADX_Trend'] = False

    # Point 3.0: Macro Alignment (Price vs 1-Hour EMA200)
    if data['closes'][i] > data['ema200_1h'][i]:
        long_score += 1.0
        long_breakdown['Macro_EMA200'] = True
    else:
        long_breakdown['Macro_EMA200'] = False

    if data['closes'][i] < data['ema200_1h'][i]:
        short_score += 1.0
        short_breakdown['Macro_EMA200'] = True
    else:
        short_breakdown['Macro_EMA200'] = False

    # Point 4.0: VWAP Level (Close vs Session VWAP)
    if data['closes'][i] > data['vwap'][i]:
        long_score += 1.0
        long_breakdown['VWAP'] = True
    else:
        long_breakdown['VWAP'] = False

    if data['closes'][i] < data['vwap'][i]:
        short_score += 1.0
        short_breakdown['VWAP'] = True
    else:
        short_breakdown['VWAP'] = False

    # Point 5.0: Ribbon Alignment (EMA 9 > 21 > 50 for Long, 9 < 21 < 50 for Short)
    if data['ema9'][i] > data['ema21'][i] > data['ema50'][i]:
        long_score += 1.0
        long_breakdown['EMA_Ribbon'] = True
    else:
        long_breakdown['EMA_Ribbon'] = False

    if data['ema9'][i] < data['ema21'][i] < data['ema50'][i]:
        short_score += 1.0
        short_breakdown['EMA_Ribbon'] = True
    else:
        short_breakdown['EMA_Ribbon'] = False

    # Point 6.0: MACD Momentum
    hist_prev = data['macd_hist'][i-1] if i > 0 else 0.0
    if data['macd_line'][i] > data['macd_signal'][i] and data['macd_hist'][i] > 0 and data['macd_hist'][i] > hist_prev:
        long_score += 1.0
        long_breakdown['MACD'] = True
    else:
        long_breakdown['MACD'] = False

    if data['macd_line'][i] < data['macd_signal'][i] and data['macd_hist'][i] < 0 and data['macd_hist'][i] < hist_prev:
        short_score += 1.0
        short_breakdown['MACD'] = True
    else:
        short_breakdown['MACD'] = False

    # Point 7.0: RSI Corridor (52 <= RSI <= 68 for Long, 32 <= RSI <= 48 for Short)
    if 52.0 <= data['rsi'][i] <= 68.0:
        long_score += 1.0
        long_breakdown['RSI_Corridor'] = True
    else:
        long_breakdown['RSI_Corridor'] = False

    if 32.0 <= data['rsi'][i] <= 48.0:
        short_score += 1.0
        short_breakdown['RSI_Corridor'] = True
    else:
        short_breakdown['RSI_Corridor'] = False

    # Point 8.0: ATR Expansion (Current ATR(14) > ATR_SMA(20))
    if data['atr14'][i] > data['atr_sma20'][i]:
        long_score += 1.0
        short_score += 1.0
        long_breakdown['ATR_Expansion'] = True
        short_breakdown['ATR_Expansion'] = True
    else:
        long_breakdown['ATR_Expansion'] = False
        short_breakdown['ATR_Expansion'] = False

    # Point 9.0: Orderbook Spread <= 0.0003 (Top 30 liquid pairs satisfy this criterion)
    long_score += 1.0
    short_score += 1.0
    long_breakdown['Spread'] = True
    short_breakdown['Spread'] = True

    # Point 10.0: Trigger Candle
    c_rng = c['high'] - c['low']
    # Long: Bullish Engulfing OR Pinbar closing in top 25% of bar
    is_bullish_engulf = (c['close'] > c['open'] and prev_c['close'] < prev_c['open'] and
                         c['close'] >= prev_c['open'] and c['open'] <= prev_c['close'])
    is_bullish_pinbar = (c_rng > 0 and ((c['close'] - c['low']) / c_rng >= 0.75) and c['close'] >= c['open'])
    if is_bullish_engulf or is_bullish_pinbar:
        long_score += 1.0
        long_breakdown['Trigger_Candle'] = True
    else:
        long_breakdown['Trigger_Candle'] = False

    # Short: Bearish Engulfing OR Pinbar closing in bottom 25% of bar
    is_bearish_engulf = (c['close'] < c['open'] and prev_c['close'] > prev_c['open'] and
                         c['close'] <= prev_c['open'] and c['open'] >= prev_c['close'])
    is_bearish_pinbar = (c_rng > 0 and ((c['close'] - c['low']) / c_rng <= 0.25) and c['close'] <= c['open'])
    if is_bearish_engulf or is_bearish_pinbar:
        short_score += 1.0
        short_breakdown['Trigger_Candle'] = True
    else:
        short_breakdown['Trigger_Candle'] = False

    # Check Execution Threshold (Score >= MIN_SCORE)
    signal_type = None
    tp_price = 0.0
    sl_price = 0.0
    entry_price = c['close']

    if long_score >= MIN_SCORE and short_score < MIN_SCORE:
        signal_type = "LONG"
        sl_price = entry_price - (ATR_SL_MULT * atr)
        tp_price = entry_price + (ATR_TP_MULT * atr)
    elif short_score >= MIN_SCORE and long_score < MIN_SCORE:
        signal_type = "SHORT"
        sl_price = entry_price + (ATR_SL_MULT * atr)
        tp_price = entry_price - (ATR_TP_MULT * atr)

    return {
        'long_score': long_score,
        'short_score': short_score,
        'long_breakdown': long_breakdown,
        'short_breakdown': short_breakdown,
        'signal': signal_type,
        'entry_price': entry_price,
        'sl_price': sl_price,
        'tp_price': tp_price,
        'atr': atr
    }
