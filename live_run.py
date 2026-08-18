"""
Point d'entrée pour l'exécution PÉRIODIQUE en autonomie (via GitHub Actions).

Contrairement à main.py (qui rejoue tout un historique d'un coup pour le backtest),
ce script :
1. Charge l'état persistant du portefeuille (state/bot_state.json)
2. Récupère les données récentes nécessaires (juste assez pour calculer la moyenne mobile)
3. Évalue UN signal sur la dernière bougie
4. Exécute le trade si signal (en paper trading — aucun ordre réel envoyé)
5. Sauvegarde le nouvel état
6. Envoie une notification Telegram si un trade a eu lieu, + un résumé une fois par jour

Conçu pour être relancé toutes les ~15 min sans état en mémoire entre les appels.
"""
from datetime import datetime, timezone

import config
from data_fetcher import fetch_ohlcv
from strategy import add_indicators, GridTrendStrategy
from state_manager import load_state, save_state, append_trade_log
from telegram_notifier import notify_trade, notify_daily_summary, notify_error


def run_once():
    try:
        # On récupère un peu plus que TREND_MA_PERIOD bougies pour que la moyenne mobile soit valide
        lookback_days = max(10, (config.TREND_MA_PERIOD // 24) + 5)
        df = fetch_ohlcv(since_days=lookback_days)
        df = add_indicators(df)
        df = df.dropna(subset=["trend_ma"])

        if df.empty:
            notify_error("Pas assez de données pour calculer les indicateurs, run ignoré.")
            return

        latest_row = df.iloc[-1]
        current_price = latest_row["close"]

        state = load_state(fallback_center_price=current_price)

        strat = GridTrendStrategy(state["center_price"])
        strat.open_grid_positions = state["open_grid_positions"]

        signal = strat.generate_signal(latest_row)

        if signal["action"] == "BUY" and state["cash"] >= signal["size_usd"]:
            fee = signal["size_usd"] * config.FEE_RATE
            btc_bought = (signal["size_usd"] - fee) / signal["price"]
            state["cash"] -= signal["size_usd"]
            state["btc_holdings"] += btc_bought
            trade = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "BUY", "price": signal["price"],
                "size_usd": signal["size_usd"], "fee": fee, "btc_amount": btc_bought,
            }
            append_trade_log(trade)
            notify_trade("BUY", signal["price"], signal["size_usd"], state["cash"], state["btc_holdings"])
            print(f"BUY exécuté @ {signal['price']}")

        elif signal["action"] == "SELL" and state["btc_holdings"] > 0:
            btc_to_sell = min(signal["size_usd"] / signal["price"], state["btc_holdings"])
            proceeds = btc_to_sell * signal["price"]
            fee = proceeds * config.FEE_RATE
            state["cash"] += proceeds - fee
            state["btc_holdings"] -= btc_to_sell
            trade = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "SELL", "price": signal["price"],
                "size_usd": proceeds, "fee": fee, "btc_amount": btc_to_sell,
            }
            append_trade_log(trade)
            notify_trade("SELL", signal["price"], proceeds, state["cash"], state["btc_holdings"])
            print(f"SELL exécuté @ {signal['price']}")

        else:
            print(f"Aucun signal @ {current_price} — rien à faire ce run.")

        # Met à jour les positions ouvertes du grid dans l'état persistant
        state["open_grid_positions"] = strat.open_grid_positions

        # Résumé quotidien Telegram (une seule fois par jour, pas à chaque run)
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if state.get("last_summary_date") != today_str:
            equity = state["cash"] + state["btc_holdings"] * current_price
            report = {
                "date": today_str,
                "prix_btc": round(current_price, 2),
                "cash_usd": round(state["cash"], 2),
                "btc_detenu": round(state["btc_holdings"], 6),
                "equite_totale_usd": round(equity, 2),
                "positions_grid_ouvertes": len(state["open_grid_positions"]),
            }
            sent_ok = notify_daily_summary(report)
            if sent_ok:
                state["last_summary_date"] = today_str
            else:
                print("Résumé quotidien non envoyé — nouvelle tentative au prochain run.")

        save_state(state)

    except Exception as e:
        notify_error(str(e))
        raise


if __name__ == "__main__":
    run_once()
