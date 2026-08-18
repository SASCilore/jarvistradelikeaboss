"""
Gère la sauvegarde/chargement de l'état du bot entre deux exécutions.
"""
import json
import os
from datetime import datetime, timezone

import config

STATE_PATH = "state/bot_state.json"


def default_state(center_price: float) -> dict:
    return {
        "cash": config.STARTING_BALANCE_USD,
        "btc_holdings": 0.0,
        "center_price": center_price,
        "open_grid_positions": [],
        "last_summary_date": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run_at": None,
    }


def load_state(fallback_center_price: float) -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    print("Aucun état existant trouvé, initialisation d'un nouvel état.")
    return default_state(fallback_center_price)


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    print(f"État sauvegardé dans {STATE_PATH}")


def append_trade_log(trade: dict, path: str = "state/trades_history.csv"):
    """Ajoute une ligne au journal complet des trades (append-only, jamais écrasé)."""
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file_exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(trade.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(trade)


def append_equity_snapshot(timestamp: str, price: float, cash: float, btc_holdings: float,
                            path: str = "state/equity_history.csv"):
    """Enregistre la valeur totale du portefeuille à CHAQUE run (trade ou non)."""
    import csv
    equity = cash + btc_holdings * price
    row = {
        "timestamp": timestamp,
        "btc_price": round(price, 2),
        "cash": round(cash, 2),
        "btc_holdings": round(btc_holdings, 8),
        "equity": round(equity, 2),
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file_exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
