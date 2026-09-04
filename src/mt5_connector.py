import logging
import os

import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


def connect():
    login = int(os.environ["MT5_LOGIN"])
    password = os.environ["MT5_PASSWORD"]
    server = os.environ["MT5_SERVER"]
    terminal_path = os.environ.get("MT5_TERMINAL_PATH")

    kwargs = {"login": login, "password": password, "server": server}
    if terminal_path:
        kwargs["path"] = terminal_path

    if not mt5.initialize(**kwargs):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    account = mt5.account_info()
    if account is None:
        mt5.shutdown()
        raise RuntimeError(f"Could not fetch account info: {mt5.last_error()}")

    logger.info(
        "Connected to MT5: login=%s server=%s balance=%.2f %s",
        account.login, account.server, account.balance, account.currency,
    )

    if not account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO:
        logger.warning(
            "Connected account is NOT a demo account (trade_mode=%s). "
            "Live money is at risk.", account.trade_mode,
        )

    return account


def disconnect():
    mt5.shutdown()
