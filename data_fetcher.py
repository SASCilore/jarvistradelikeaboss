"""
Récupération des données de marché (OHLCV) depuis Kraken via ccxt.
Aucune clé API n'est nécessaire pour les données publiques historiques.
"""
import time
import pandas as pd
import ccxt

import config


def fetch_ohlcv(symbol: str = config.SYMBOL,
                 timeframe: str = config.TIMEFRAME,
                 since_days: int = 365,
                 exchange_id: str = config.EXCHANGE) -> pd.DataFrame:
    """
    Récupère l'historique OHLCV et le retourne sous forme de DataFrame pandas.
    """
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({"enableRateLimit": True})

    since = exchange.milliseconds() - since_days * 24 * 60 * 60 * 1000
    all_candles = []

    print(f"Récupération de {since_days} jours de données {symbol} ({timeframe}) sur {exchange_id}...")

    while True:
        candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=720)
        if not candles:
            break
        all_candles += candles
        since = candles[-1][0] + 1
        if since >= exchange.milliseconds():
            break
        time.sleep(exchange.rateLimit / 1000)

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df.drop_duplicates(inplace=True)

    print(f"-> {len(df)} bougies récupérées, de {df.index.min()} à {df.index.max()}")
    return df


def save_to_csv(df: pd.DataFrame, path: str = "data/btc_usd_history.csv"):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path)
    print(f"Données sauvegardées dans {path}")


if __name__ == "__main__":
    df = fetch_ohlcv(since_days=365)
    save_to_csv(df)
