"""
Lightweight bar-by-bar backtest of the bot's exact entry logic over recent
history. Pulls historical rates from your connected MT5 terminal (no trades
are placed). Use this to sanity-check trade frequency and R-multiple quality
before running the live bot.

Note: this shows the *raw* signal frequency/quality of the strategy, ignoring
the live bot's max_trades_per_day cap and session filter.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from dotenv import load_dotenv

from src import mt5_connector, strategy
from src.bot import ROOT, load_config
from src.data import TIMEFRAME_MAP

import MetaTrader5 as mt5


def get_rates_range(symbol, timeframe_name, start, end):
    rates = mt5.copy_rates_range(symbol, TIMEFRAME_MAP[timeframe_name], start, end)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No rates for {symbol}/{timeframe_name}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def backtest_symbol(symbol, cfg, days=90):
    s = cfg["strategy"]
    end = datetime.now()
    start = end - timedelta(days=days + 30)  # extra warmup for H1 EMA200

    df_h1 = get_rates_range(symbol, cfg["timeframes"]["trend"], start, end)
    df_m15 = get_rates_range(symbol, cfg["timeframes"]["entry"], start, end)

    df_h1["ema_fast"] = strategy.ema(df_h1["close"], s["trend_ema_fast"])
    df_h1["ema_slow"] = strategy.ema(df_h1["close"], s["trend_ema_slow"])
    df_h1["bias"] = None
    df_h1.loc[df_h1["ema_fast"] > df_h1["ema_slow"], "bias"] = "up"
    df_h1.loc[df_h1["ema_fast"] < df_h1["ema_slow"], "bias"] = "down"

    df_m15["ema_fast"] = strategy.ema(df_m15["close"], s["entry_ema_fast"])
    df_m15["ema_slow"] = strategy.ema(df_m15["close"], s["entry_ema_slow"])
    df_m15["rsi"] = strategy.rsi(df_m15["close"], s["rsi_period"])
    df_m15["atr"] = strategy.atr(df_m15, s["atr_period"])

    bias_series = df_h1[["time", "bias"]].dropna().sort_values("time")
    df_m15 = pd.merge_asof(
        df_m15.sort_values("time"), bias_series, on="time", direction="backward"
    )

    cutoff = start + timedelta(days=30)
    df_m15 = df_m15[df_m15["time"] >= cutoff].reset_index(drop=True)

    trades = []
    open_trade = None  # (direction, entry, sl, tp, entry_time)

    for i in range(2, len(df_m15) - 1):
        row = df_m15.iloc[i]
        prev = df_m15.iloc[i - 1]

        if open_trade is not None:
            direction, entry, sl, tp, entry_time = open_trade
            hi, lo = row["high"], row["low"]
            hit_sl = lo <= sl if direction == "buy" else hi >= sl
            hit_tp = hi >= tp if direction == "buy" else lo <= tp
            if hit_sl or hit_tp:
                # if both touched in the same bar, conservatively assume SL first
                exit_price = sl if hit_sl else tp
                r_multiple = -1.0 if hit_sl else (s["atr_tp_multiplier"] / s["atr_sl_multiplier"])
                trades.append({
                    "symbol": symbol, "direction": direction,
                    "entry_time": entry_time, "exit_time": row["time"],
                    "entry": entry, "exit": exit_price, "r": r_multiple,
                })
                open_trade = None
            continue

        bias = row["bias"]
        if bias not in ("up", "down"):
            continue

        crossed_up = prev["ema_fast"] <= prev["ema_slow"] and row["ema_fast"] > row["ema_slow"]
        crossed_down = prev["ema_fast"] >= prev["ema_slow"] and row["ema_fast"] < row["ema_slow"]

        signal = None
        if bias == "up" and crossed_up and row["rsi"] < s["rsi_upper"]:
            signal = "buy"
        elif bias == "down" and crossed_down and row["rsi"] > s["rsi_lower"]:
            signal = "sell"
        if signal is None:
            continue

        entry = row["close"]
        atr_val = row["atr"]
        sl_dist = atr_val * s["atr_sl_multiplier"]
        tp_dist = atr_val * s["atr_tp_multiplier"]
        sl = entry - sl_dist if signal == "buy" else entry + sl_dist
        tp = entry + tp_dist if signal == "buy" else entry - tp_dist
        open_trade = (signal, entry, sl, tp, row["time"])

    return pd.DataFrame(trades)


def main():
    load_dotenv(ROOT / ".env")
    cfg = load_config()
    mt5_connector.connect()
    try:
        days = 90
        all_trades = []
        for symbol in cfg["symbols"]:
            print(f"Backtesting {symbol} over last {days} days...")
            all_trades.append(backtest_symbol(symbol, cfg, days=days))

        combined = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
        if combined.empty:
            print("No trades generated in backtest window.")
            return

        combined = combined.sort_values("entry_time")
        n_days = (combined["entry_time"].max() - combined["entry_time"].min()).days or 1
        win_rate = (combined["r"] > 0).mean()
        total_r = combined["r"].sum()

        print("\n=== Backtest summary (raw signals, no daily cap/session filter applied) ===")
        print(f"Symbols: {', '.join(cfg['symbols'])}")
        print(f"Period: {combined['entry_time'].min()} -> {combined['entry_time'].max()} ({n_days} days)")
        print(f"Total trades: {len(combined)}  |  Avg trades/day: {len(combined) / n_days:.2f}")
        print(f"Win rate: {win_rate:.1%}")
        print(f"Total R: {total_r:.2f}  |  Avg R/trade: {combined['r'].mean():.2f}")
    finally:
        mt5_connector.disconnect()


if __name__ == "__main__":
    main()
