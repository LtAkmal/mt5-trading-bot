import numpy as np
import pandas as pd


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def trend_bias(df_h1, fast=50, slow=200):
    """Higher-timeframe trend direction from EMA structure: 'up', 'down', or None."""
    close = df_h1["close"]
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    if ema_fast.iloc[-1] > ema_slow.iloc[-1]:
        return "up"
    if ema_fast.iloc[-1] < ema_slow.iloc[-1]:
        return "down"
    return None


def entry_signal(df_m15, bias, rsi_period=14, fast=9, slow=21, rsi_upper=70, rsi_lower=30):
    """
    EMA(fast)/EMA(slow) crossover on the last CLOSED candle (index -2), taken only
    in the direction of `bias` and filtered by RSI to avoid exhausted moves.
    Returns 'buy', 'sell', or None.
    """
    close = df_m15["close"]
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    rsi_val = rsi(close, rsi_period)

    cur, prev = -2, -3
    crossed_up = ema_fast.iloc[prev] <= ema_slow.iloc[prev] and ema_fast.iloc[cur] > ema_slow.iloc[cur]
    crossed_down = ema_fast.iloc[prev] >= ema_slow.iloc[prev] and ema_fast.iloc[cur] < ema_slow.iloc[cur]

    if bias == "up" and crossed_up and rsi_val.iloc[cur] < rsi_upper:
        return "buy"
    if bias == "down" and crossed_down and rsi_val.iloc[cur] > rsi_lower:
        return "sell"
    return None
