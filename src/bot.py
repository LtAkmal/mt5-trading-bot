import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5
import yaml
from dotenv import load_dotenv

from . import data, executor, mt5_connector, risk, strategy

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "config.yaml"
LOG_PATH = ROOT / "logs" / "bot.log"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def in_session(cfg):
    now = datetime.now(timezone.utc)
    return cfg["session"]["start_hour"] <= now.hour < cfg["session"]["end_hour"]


def process_symbol(symbol, cfg, magic, last_signal_bar, logger):
    if not mt5.symbol_select(symbol, True):
        logger.warning("Could not select symbol %s", symbol)
        return False

    if executor.has_open_position(symbol, magic):
        return False

    s = cfg["strategy"]
    df_h1 = data.get_rates(symbol, cfg["timeframes"]["trend"], count=s["trend_ema_slow"] + 50)
    df_m15 = data.get_rates(symbol, cfg["timeframes"]["entry"], count=200)

    last_closed_time = df_m15["time"].iloc[-2]
    if last_signal_bar.get(symbol) == last_closed_time:
        return False  # already acted on (or skipped) this closed bar

    bias = strategy.trend_bias(df_h1, s["trend_ema_fast"], s["trend_ema_slow"])
    if bias is None:
        return False

    signal = strategy.entry_signal(
        df_m15, bias,
        rsi_period=s["rsi_period"], fast=s["entry_ema_fast"], slow=s["entry_ema_slow"],
        rsi_upper=s["rsi_upper"], rsi_lower=s["rsi_lower"],
    )
    if signal is None:
        return False

    atr_val = strategy.atr(df_m15, s["atr_period"]).iloc[-2]
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if signal == "buy" else tick.bid

    sl_dist = atr_val * s["atr_sl_multiplier"]
    tp_dist = atr_val * s["atr_tp_multiplier"]
    sl_price = price - sl_dist if signal == "buy" else price + sl_dist
    tp_price = price + tp_dist if signal == "buy" else price - tp_dist

    balance = mt5.account_info().balance
    lot = risk.calc_lot_size(symbol, balance, cfg["risk"]["risk_pct_per_trade"], sl_dist)

    last_signal_bar[symbol] = last_closed_time  # mark bar as handled either way

    if lot <= 0:
        logger.warning("Computed lot size <= 0 for %s, skipping signal", symbol)
        return False

    result = executor.place_market_order(
        symbol, signal, lot, sl_price, tp_price, magic,
        comment="ema-trend-bot",
        deviation=cfg["execution"]["deviation_points"],
    )
    return result is not None


def run():
    LOG_PATH.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_PATH)],
    )
    logger = logging.getLogger("bot")

    load_dotenv(ROOT / ".env")
    cfg = load_config()
    mt5_connector.connect()

    magic = cfg["execution"]["magic_number"]
    poll = cfg["execution"]["poll_interval_seconds"]
    last_signal_bar = {}

    try:
        while True:
            trades_today = executor.todays_trade_count(magic)
            pnl_today = executor.todays_pnl(magic)
            balance = mt5.account_info().balance

            if pnl_today <= -abs(cfg["risk"]["max_daily_loss_pct"]) * balance:
                logger.warning("Daily loss limit hit (%.2f). Standing down for today.", pnl_today)
                time.sleep(poll)
                continue

            if trades_today >= cfg["risk"]["max_trades_per_day"]:
                time.sleep(poll)
                continue

            if not in_session(cfg):
                time.sleep(poll)
                continue

            for symbol in cfg["symbols"]:
                if executor.todays_trade_count(magic) >= cfg["risk"]["max_trades_per_day"]:
                    break
                try:
                    process_symbol(symbol, cfg, magic, last_signal_bar, logger)
                except Exception:
                    logger.exception("Error processing %s", symbol)

            time.sleep(poll)
    except KeyboardInterrupt:
        logger.info("Shutting down (keyboard interrupt).")
    finally:
        mt5_connector.disconnect()
