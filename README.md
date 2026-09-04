# trading-bot

A Python trading bot for MetaTrader 5, using the official `MetaTrader5` package
to connect to a locally running MT5 terminal, generate signals, and place
trades with automatic position sizing and daily risk controls.

**Everything for this project — code, config, logs — lives in this folder.**

## Strategy: EMA trend + pullback

- **Trend filter (H1):** EMA50 vs EMA200 — only trade in the direction of the
  higher-timeframe trend.
- **Entry (M15):** EMA9/EMA21 crossover in the trend direction, filtered by
  RSI(14) so entries aren't taken into an already-exhausted move.
- **Stop / target:** ATR(14)-based — 1.5x ATR stop, 2.5x ATR target
  (~1.7:1 reward-to-risk).
- **Position sizing:** risks a fixed 1% of account balance per trade, computed
  from the stop distance and the broker's tick value (works for forex,
  metals, indices, etc.).
- **Daily discipline:**
  - Hard cap of **3 trades/day** on XAUUSD (gold) — the cap survives bot
    restarts because it's recomputed from MT5's own trade history, not just
    an in-memory counter.
  - Daily loss circuit-breaker (default -3% of balance) stops new entries
    for the rest of the day.
  - Session filter (default 07:00-20:00 UTC, the London/NY window) avoids
    thin, noisy hours.

All of the above is tunable in [config/config.yaml](config/config.yaml)
without touching any code.

**Symbol: XAUUSD (gold) only.** Gold moves in much bigger absolute price
swings than a forex pair — that's handled automatically since position
sizing (`src/risk.py`) uses the broker's own tick value/size rather than a
pip formula, and stops/targets are ATR-based so they scale with gold's
volatility on their own. Gold is also more prone to sharp, news-driven
spikes (NFP, CPI, Fed decisions, geopolitical headlines) than a typical
major pair, so treat the ATR stop as a floor, not a guarantee — slippage on
fast moves is real even on a good broker. Since only one symbol is scanned,
don't be surprised if some days produce fewer than 3 signals; the cap is a
ceiling; it won't manufacture trades that aren't there.

Double-check the exact symbol name your broker uses — `XAUUSD` is common,
but some brokers use `XAUUSD.a`, `GOLD`, or `XAUUSDm`.
`scripts/check_connection.py` will tell you immediately if the configured
name isn't recognized.

This is a solid, risk-aware starting template — not a proven profitable
system. Backtest and forward-test on demo (which you're already set up for)
before ever considering live money.

## Project layout

```
trading-bot/
  config/config.yaml      strategy, risk, session, execution parameters
  src/
    mt5_connector.py       connect/disconnect to the MT5 terminal
    data.py                historical rate fetching
    strategy.py             EMA/RSI/ATR + signal generation logic
    risk.py                 position sizing
    executor.py              order placement, daily trade/PnL tracking
    bot.py                  main loop tying it all together
  scripts/
    check_connection.py     verify MT5 login + symbols (no trading)
    backtest.py             backtest the strategy on recent history (no trading)
    run_bot.py               starts the live bot loop (places real demo trades)
  logs/bot.log              runtime log (created on first run)
  .env.example              template for your MT5 credentials
  .env                      your actual credentials (you create this, gitignored)
```

## Setup

1. **Install dependencies** (Python 3.9+ recommended):

   ```bash
   cd trading-bot
   pip install -r requirements.txt
   ```

2. **Create your `.env`** from the template and fill in your demo account
   details (found in MT5: `Tools > Options > Server`, or your broker's login
   email):

   ```bash
   cp .env.example .env
   ```

   Edit `.env`:
   ```
   MT5_LOGIN=your_demo_login_number
   MT5_PASSWORD=your_demo_password
   MT5_SERVER=YourBroker-Demo
   ```

   `.env` is gitignored — never commit real credentials.

3. **Make sure the MT5 desktop terminal is installed and closed or open**
   (the Python package can launch/attach to it automatically). If it's
   installed somewhere non-standard, set `MT5_TERMINAL_PATH` in `.env`.

4. **Check symbol names.** Some brokers suffix symbols (e.g. `EURUSD.a`,
   `EURUSDm`). Run the connection check first — it will tell you if a
   configured symbol isn't recognized, so you can fix `config/config.yaml`.

## Running

**1. Verify the connection (no trading):**

```bash
python scripts/check_connection.py
```

Confirms login, balance, demo/live status, and that each configured symbol
is tradeable from your broker.

**2. Backtest the strategy on recent history (no trading):**

```bash
python scripts/backtest.py
```

Runs the exact entry/exit logic bar-by-bar over the last ~90 days per symbol
and reports trade count, average trades/day, win rate, and total R. Use this
to sanity-check the strategy before running it live.

**3. Run the live bot (places real trades on your connected account):**

```bash
python scripts/run_bot.py
```

Runs continuously, polling every 30s (configurable), only acting once per
newly closed candle. Stop with `Ctrl+C`. All activity is logged to
`logs/bot.log` and the console.

> Even though this targets your demo account, `run_bot.py` will place real
> orders on whatever account is in `.env`. Double-check `MT5_LOGIN` before
> running, and never point this at a live account without fully
> understanding and testing the strategy first.

## Tuning

Everything in `config/config.yaml` is safe to adjust without touching code:

- `symbols` — basket of instruments to scan for setups.
- `strategy.*` — EMA/RSI/ATR periods and multipliers.
- `risk.risk_pct_per_trade` — % of balance risked per trade.
- `risk.max_trades_per_day` — daily trade cap (default 3).
- `risk.max_daily_loss_pct` — daily loss circuit-breaker.
- `session.start_hour` / `end_hour` — trading window in UTC.
- `execution.poll_interval_seconds` — how often the bot checks for new bars.

## Disclaimer

This is a template for learning and experimentation. Trading carries real
financial risk. Nothing here is financial advice, and past backtest
performance does not guarantee future results. Test thoroughly on demo,
understand every part of the logic, and only risk money you can afford to
lose.
