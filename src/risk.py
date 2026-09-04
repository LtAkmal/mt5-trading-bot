import MetaTrader5 as mt5


def calc_lot_size(symbol, balance, risk_pct, sl_distance_price):
    """
    Position size such that a full stop-out loses ~risk_pct of balance.
    Uses the broker's tick value/size so it works for forex, metals, indices, etc.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"symbol_info failed for {symbol}: {mt5.last_error()}")

    tick_value = info.trade_tick_value
    tick_size = info.trade_tick_size
    if not tick_size or not tick_value:
        raise RuntimeError(f"Invalid tick size/value for {symbol}")

    risk_amount = balance * risk_pct
    money_per_lot = (sl_distance_price / tick_size) * tick_value
    if money_per_lot <= 0:
        raise RuntimeError(f"Non-positive money_per_lot for {symbol}")

    raw_lot = risk_amount / money_per_lot

    step = info.volume_step or 0.01
    lot = round(raw_lot / step) * step
    lot = max(info.volume_min, min(info.volume_max, lot))
    return round(lot, 2)
