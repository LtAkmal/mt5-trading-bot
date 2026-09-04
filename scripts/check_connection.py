import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import MetaTrader5 as mt5
from dotenv import load_dotenv

from src import mt5_connector
from src.bot import ROOT, load_config


def main():
    load_dotenv(ROOT / ".env")
    cfg = load_config()
    account = mt5_connector.connect()
    try:
        print(f"Login:   {account.login}")
        print(f"Server:  {account.server}")
        print(f"Balance: {account.balance} {account.currency}")
        print(f"Demo:    {account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO}")
        print()
        for symbol in cfg["symbols"]:
            ok = mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if ok and info and tick:
                print(
                    f"{symbol}: OK  bid={tick.bid} ask={tick.ask} "
                    f"min_lot={info.volume_min} step={info.volume_step}"
                )
            else:
                print(f"{symbol}: NOT AVAILABLE from this broker (check symbol name/suffix)")
    finally:
        mt5_connector.disconnect()


if __name__ == "__main__":
    main()
