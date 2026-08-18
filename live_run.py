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
