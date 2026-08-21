"""
Exécution périodique du bot FOREX (EUR/USD via IG). Contrairement au bot BTC/Kraken
qui retélécharge tout à chaque run (API publique sans quota), ce script maintient
son propre historique local dans le repo et ne récupère que quelques bougies
fraîches à chaque réveil — indispensable vu le quota IG de 10 000 points/semaine.
"""
from datetime import datetime, timezone
import pandas as pd

import config
from ig_fetcher import get_ig_service, fetch_ohlcv_ig
from strategy import add_indicators, GridTrendStrategy
from state_manager_forex import (
    load_forex_state, save_forex_state, merge_price_history, merge_daily_history,
    append_forex_trade_log, append_forex_equity_snapshot,
)
from telegram_notifier import notify_trade, notify_daily_summary, notify_error


def compute_htf_uptrend_from_daily(daily_df: pd.DataFrame) -> bool:
    """Calcule la tendance journalière à partir de l'historique journalier maintenu."""
    if not config.HTF_TREND_ENABLED:
        return True
    if len(daily_df) < config.HTF_MA_PERIOD:
        return True
    ma = daily_df["close"].rolling(config.HTF_MA_PERIOD).mean()
    last_ma = ma.iloc[-1]
    if pd.isna(last_ma):
        return True
    return bool(daily_df["close"].iloc[-1] > last_ma)


def run_once():
    try:
        ig_service = get_ig_service()

        new_candles = fetch_ohlcv_ig(ig_service, config.FOREX_EPIC, resolution="15Min", num_points=10)
        df = merge_price_history(new_candles)
        print(f"Historique 15min maintenu : {len(df)} bougies (dont {len(new_candles)} récupérées ce run)")

        new_daily = fetch_ohlcv_ig(ig_service, config.FOREX_EPIC, resolution="D", num_points=5)
        daily_df = merge_daily_history(new_daily)
        print(f"Historique journalier maintenu : {len(daily_df)} jours")

        df = add_indicators(df)
        df_ready = df.dropna(subset=["atr"])

        if df_ready.empty:
            notify_error("Pas assez d'historique accumulé pour l'ATR — run ignoré, réessaiera au prochain cycle.")
            return

        latest_row = df_ready.iloc[-1].copy()
        current_price = latest_row["close"]

        latest_row["htf_uptrend"] = compute_htf_uptrend_from_daily(daily_df)

        state = load_forex_state(fallback_center_price=current_price)

        strat = GridTrendStrategy(state["center_price"])
        strat.open_grid_positions = state["open_grid_positions"]

        signal = strat.generate_signal(latest_row)

        if signal["action"] == "BUY" and state["cash"] >= signal["size_usd"]:
            fee = signal["size_usd"] * config.FOREX_FEE_RATE
            net_units = (signal["size_usd"] - fee) / signal["price"]
            state["cash"] -= signal["size_usd"]
            state["asset_holdings"] += net_units
            trade = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "BUY", "price": signal["price"], "direction": signal.get("direction", ""),
                "reason": signal.get("reason", ""),
                "size_usd": signal["size_usd"], "fee": fee, "units": net_units,
            }
            append_forex_trade_log(trade)
            notify_trade("BUY", signal["price"], signal["size_usd"], state["cash"], state["asset_holdings"])
            print(f"BUY exécuté @ {signal['price']} ({signal.get('direction','')} {signal.get('reason','')})")

        elif signal["action"] == "SELL":
            units = signal["size_usd"] / signal["price"]
            proceeds = signal["size_usd"]
            fee = proceeds * config.FOREX_FEE_RATE
            state["cash"] += proceeds - fee
            state["asset_holdings"] -= units
            trade = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "SELL", "price": signal["price"], "direction": signal.get("direction", ""),
                "reason": signal.get("reason", ""),
                "size_usd": proceeds, "fee": fee, "units": units,
            }
            append_forex_trade_log(trade)
            notify_trade("SELL", signal["price"], proceeds, state["cash"], state["asset_holdings"])
            print(f"SELL exécuté @ {signal['price']} ({signal.get('direction','')} {signal.get('reason','')})")

        else:
            print(f"Aucun signal @ {current_price} — rien à faire ce run.")

        state["open_grid_positions"] = strat.open_grid_positions
        state["center_price"] = strat.center_price

        run_timestamp = datetime.now(timezone.utc).isoformat()
        append_forex_equity_snapshot(run_timestamp, current_price, state["cash"], state["asset_holdings"])

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if state.get("last_summary_date") != today_str:
            equity = state["cash"] + state["asset_holdings"] * current_price
            report = {
                "date": today_str,
                "prix_eurusd": round(current_price, 5),
                "cash_usd": round(state["cash"], 2),
                "positions_grid_ouvertes": len(state["open_grid_positions"]),
                "equite_totale_usd": round(equity, 2),
            }
            sent_ok = notify_daily_summary(report)
            if sent_ok:
                state["last_summary_date"] = today_str

        save_forex_state(state)

    except Exception as e:
        notify_error(f"[Forex] {str(e)}")
        raise


if __name__ == "__main__":
    run_once()
