import logging
from datetime import datetime, timedelta

import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


def has_open_position(symbol, magic):
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return False
    return any(p.magic == magic for p in positions)


def _today_range():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    return start, now + timedelta(days=1)


def todays_trade_count(magic):
    """Count trades OPENED today with this magic number (survives bot restarts)."""
    start, end = _today_range()
    deals = mt5.history_deals_get(start, end)
    if not deals:
        return 0
    return len([d for d in deals if d.magic == magic and d.entry == mt5.DEAL_ENTRY_IN])


def todays_pnl(magic):
    """Net realized P&L today (profit + swap + commission) for closed deals with this magic number."""
    start, end = _today_range()
    deals = mt5.history_deals_get(start, end)
    if not deals:
        return 0.0
    closed = [d for d in deals if d.magic == magic and d.entry == mt5.DEAL_ENTRY_OUT]
    return sum(d.profit + d.swap + d.commission for d in closed)


def place_market_order(symbol, direction, lot, sl_price, tp_price, magic, comment, deviation=20):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"No tick data for {symbol}: {mt5.last_error()}")

    order_type = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
    price = tick.ask if direction == "buy" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error("order_send failed for %s: %s", symbol, result)
        return None

    logger.info(
        "Order filled: %s %s %.2f lots @ %.5f SL=%.5f TP=%.5f",
        symbol, direction, lot, price, sl_price, tp_price,
    )
    return result
