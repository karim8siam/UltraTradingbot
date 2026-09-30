import math

def calc_ema(series, span):
    if not series:
        return []
    alpha = 2.0 / (span + 1.0)
    ema = [series[0]]
    for i in range(1, len(series)):
        ema.append(alpha * series[i] + (1 - alpha) * ema[-1])
    return ema

def calc_all_indicators(candles, timeframe="30m"):
    n = len(candles)
    if n < 100:
        return None

    closes = [c['close'] for c in candles]
    highs = [c['high'] for c in candles]
    lows = [c['low'] for c in candles]
    opens = [c['open'] for c in candles]
    volumes = [c['volume'] for c in candles]

    # 1. EMAs (9, 21, 50)
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    ema50 = calc_ema(closes, 50)

    # 1-Hour EMA 200 mapping
    if timeframe == '5m':
        macro_period = min(n, 2400)  # 12 x 200
        vwap_window = 288
    elif timeframe == '15m':
        macro_period = min(n, 800)   # 4 x 200
        vwap_window = 96
    else:  # 30m default
        macro_period = min(n, 400)   # 2 x 200
        vwap_window = 48

    ema200_1h = calc_ema(closes, macro_period)

    # 2. 20-period Volume SMA (for RVOL)
    vol_sma20 = [0.0] * n
    for i in range(n):
        if i >= 19:
            vol_sma20[i] = sum(volumes[i-19:i+1]) / 20.0
        else:
            vol_sma20[i] = sum(volumes[:i+1]) / (i + 1)

    # 3. ATR(14) and 20-period ATR SMA
    tr = [0.0] * n
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        h_pc = abs(highs[i] - closes[i-1])
        l_pc = abs(lows[i] - closes[i-1])
        tr[i] = max(hl, h_pc, l_pc)

    atr14 = calc_ema(tr, 14)
    atr_sma20 = [0.0] * n
    for i in range(n):
        if i >= 19:
            atr_sma20[i] = sum(atr14[i-19:i+1]) / 20.0
        else:
            atr_sma20[i] = sum(atr14[:i+1]) / (i + 1)

    # 4. RSI(14) Wilder's smoothed
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        diff = closes[i] - closes[i-1]
        if diff > 0:
            gains[i] = diff
        else:
            losses[i] = -diff

    avg_gain = [0.0] * n
    avg_loss = [0.0] * n
    rsi = [50.0] * n

    if n >= 15:
        avg_gain[14] = sum(gains[1:15]) / 14.0
        avg_loss[14] = sum(losses[1:15]) / 14.0
        if avg_loss[14] == 0:
            rsi[14] = 100.0
        else:
            rs = avg_gain[14] / avg_loss[14]
            rsi[14] = 100.0 - (100.0 / (1.0 + rs))

        for i in range(15, n):
            avg_gain[i] = (avg_gain[i-1] * 13 + gains[i]) / 14.0
            avg_loss[i] = (avg_loss[i-1] * 13 + losses[i]) / 14.0
            if avg_loss[i] == 0:
                rsi[i] = 100.0
            else:
                rs = avg_gain[i] / avg_loss[i]
                rsi[i] = 100.0 - (100.0 / (1.0 + rs))

    # 5. MACD(12, 26, 9)
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd_line = [ema12[i] - ema26[i] for i in range(n)]
    macd_signal = calc_ema(macd_line, 9)
    macd_hist = [macd_line[i] - macd_signal[i] for i in range(n)]

    # 6. ADX(14), +DI, -DI
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up_move = highs[i] - highs[i-1]
        down_move = lows[i-1] - lows[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    smooth_tr = calc_ema(tr, 14)
    smooth_plus_dm = calc_ema(plus_dm, 14)
    smooth_minus_dm = calc_ema(minus_dm, 14)

    plus_di = [0.0] * n
    minus_di = [0.0] * n
    dx = [0.0] * n
    for i in range(n):
        str_val = smooth_tr[i] if smooth_tr[i] > 1e-9 else 1e-9
        p_di = 100.0 * (smooth_plus_dm[i] / str_val)
        m_di = 100.0 * (smooth_minus_dm[i] / str_val)
        plus_di[i] = p_di
        minus_di[i] = m_di
        di_sum = p_di + m_di
        dx[i] = 100.0 * (abs(p_di - m_di) / di_sum) if di_sum > 1e-9 else 0.0

    adx14 = calc_ema(dx, 14)

    # 7. Rolling 24h Session VWAP
    vwap = [0.0] * n
    for i in range(n):
        start_idx = max(0, i - vwap_window + 1)
        pv = sum(((highs[k] + lows[k] + closes[k]) / 3.0) * volumes[k] for k in range(start_idx, i + 1))
        v = sum(volumes[k] for k in range(start_idx, i + 1))
        vwap[i] = (pv / v) if v > 1e-9 else closes[i]

    return {
        'candles': candles,
        'opens': opens, 'highs': highs, 'lows': lows, 'closes': closes, 'volumes': volumes,
        'ema9': ema9, 'ema21': ema21, 'ema50': ema50, 'ema200_1h': ema200_1h,
        'vol_sma20': vol_sma20, 'atr14': atr14, 'atr_sma20': atr_sma20,
        'rsi': rsi, 'macd_line': macd_line, 'macd_signal': macd_signal, 'macd_hist': macd_hist,
        'adx14': adx14, 'plus_di': plus_di, 'minus_di': minus_di, 'vwap': vwap
    }
