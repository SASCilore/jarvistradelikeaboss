"""
Gère l'état persistant du bot FOREX (séparé du bot BTC/Kraken) :
- L'état du portefeuille (cash, unités EUR détenues, positions ouvertes)
- L'historique de prix maintenu localement (pour éviter de retélécharger tout
  l'historique à chaque run — le quota IG de 10 000 points/semaine ne le permettrait
  pas si on rafraîchissait tout depuis zéro toutes les 15-30 min)
"""
import json
import os
import csv
import pandas as pd
from datetime import datetime, timezone

import config

FOREX_STATE_PATH = "state/forex_state.json"
FOREX_PRICE_HISTORY_PATH = "state/forex_price_history.csv"
FOREX_DAILY_HISTORY_PATH = "state/forex_daily_history.csv"
FOREX_TRADES_LOG_PATH = "state/forex_trades_history.csv"
FOREX_EQUITY_LOG_PATH = "state/forex_equity_history.csv"

MAX_HISTORY_ROWS = 350


def default_forex_state(center_price: float) -> dict:
    return {
        "cash": config.STARTING_BALANCE_USD,
        "asset_holdings": 0.0,
        "center_price": center_price,
        "open_grid_positions": [],
        "last_summary_date": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run_at": None,
    }


def load_forex_state(fallback_center_price: float) -> dict:
    if os.path.exists(FOREX_STATE_PATH):
        with open(FOREX_STATE_PATH, "r") as f:
            return json.load(f)
    print("Aucun état forex existant, initialisation.")
    return default_forex_state(fallback_center_price)


def save_forex_state(state: dict):
    os.makedirs(os.path.dirname(FOREX_STATE_PATH), exist_ok=True)
    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    with open(FOREX_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    print(f"État forex sauvegardé dans {FOREX_STATE_PATH}")


def merge_price_history(new_candles: pd.DataFrame, path: str = FOREX_PRICE_HISTORY_PATH,
                         max_rows: int = MAX_HISTORY_ROWS) -> pd.DataFrame:
    """
    Fusionne les nouvelles bougies récupérées avec l'historique déjà maintenu,
    déduplique par timestamp, garde seulement les max_rows plus récentes.
    """
    if os.path.exists(path):
        existing = pd.read_csv(path, index_col="timestamp", parse_dates=True)
        combined = pd.concat([existing, new_candles])
    else:
        combined = new_candles.copy()

    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    combined = combined.tail(max_rows)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    combined.to_csv(path)
    return combined


def merge_daily_history(new_daily_candles: pd.DataFrame, path: str = FOREX_DAILY_HISTORY_PATH,
                         max_rows: int = 80) -> pd.DataFrame:
    """Même principe que merge_price_history, pour l'historique journalier (filtre HTF)."""
    if os.path.exists(path):
        existing = pd.read_csv(path, index_col="timestamp", parse_dates=True)
        combined = pd.concat([existing, new_daily_candles])
    else:
        combined = new_daily_candles.copy()

    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    combined = combined.tail(max_rows)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    combined.to_csv(path)
    return combined


def append_forex_trade_log(trade: dict, path: str = FOREX_TRADES_LOG_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file_exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(trade.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(trade)


def append_forex_equity_snapshot(timestamp: str, price: float, cash: float, asset_holdings: float,
                                  path: str = FOREX_EQUITY_LOG_PATH):
    equity = cash + asset_holdings * price
    row = {
        "timestamp": timestamp,
        "eurusd_price": round(price, 6),
        "cash": round(cash, 2),
        "asset_holdings": round(asset_holdings, 6),
        "equity": round(equity, 2),
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file_exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
