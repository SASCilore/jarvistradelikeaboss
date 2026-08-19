"""
Connexion à l'API IG (CFD forex) et récupération des données de prix.
Remplace data_fetcher.py (Kraken/ccxt) pour la partie forex.
"""
import os
import pandas as pd
from trading_ig import IGService

import config


def get_ig_service() -> IGService:
    username = os.environ.get("IG_USERNAME")
    password = os.environ.get("IG_PASSWORD")
    api_key = os.environ.get("IG_API_KEY")

    if not username or not password or not api_key:
        raise RuntimeError(
            "Identifiants IG manquants — vérifie que IG_USERNAME, IG_PASSWORD "
            "et IG_API_KEY sont bien configurés (variables d'env ou secrets GitHub)."
        )

    ig_service = IGService(username, password, api_key, acc_type=config.IG_ACC_TYPE)
    ig_service.create_session()
    return ig_service


def find_epic(ig_service: IGService, search_term: str) -> str:
    results = ig_service.search_markets(search_term)
    print(f"Résultats de recherche pour '{search_term}':")
    for _, row in results.iterrows():
        print(f"  {row['epic']} — {row['instrumentName']}")
    return results


def fetch_current_price(ig_service: IGService, epic: str) -> dict:
    market = ig_service.fetch_market_by_epic(epic)
    snapshot = market["snapshot"]
    return {
        "bid": snapshot["bid"],
        "offer": snapshot["offer"],
        "mid": (snapshot["bid"] + snapshot["offer"]) / 2,
    }


def fetch_historical_prices(ig_service: IGService, epic: str, resolution: str, num_points: int) -> pd.DataFrame:
    """
    Récupère l'historique de prix. resolution ex: 'MINUTE_15', 'HOUR', 'DAY'.
    IG limite à 30 requêtes/minute et 10 000 points/semaine — à garder en tête
    pour ne pas demander des historiques trop longs d'un coup.
    """
    response = ig_service.fetch_historical_prices_by_epic(epic, resolution=resolution, numpoints=num_points)
    df = response["prices"]
    df = df.copy()
    df.columns = ["_".join(col).strip() if isinstance(col, tuple) else col for col in df.columns]
    return df


def fetch_ohlcv_ig(ig_service: IGService, epic: str, resolution: str = "MINUTE_15",
                    num_points: int = 500) -> pd.DataFrame:
    """
    Récupère des bougies et les formate en OHLCV standard (open/high/low/close/volume,
    indexé par timestamp) — même format que data_fetcher.fetch_ohlcv (Kraken), pour
    rester compatible avec strategy.add_indicators() et le reste du pipeline existant.

    IG fournit des prix bid ET ask séparément (pas un prix unique comme les exchanges
    crypto) — on utilise le prix moyen (mid = (bid+ask)/2) pour chaque valeur OHLC.
    Le "volume" IG représente le nombre de mises à jour de prix dans la période
    (proxy d'activité), pas un vrai volume de transactions comme en crypto.
    """
    response = ig_service.fetch_historical_prices_by_epic(epic, resolution=resolution, numpoints=num_points)
    raw = response["prices"]

    df = pd.DataFrame(index=raw.index)
    for col in ["Open", "High", "Low", "Close"]:
        bid = raw[("bid", col)]
        ask = raw[("ask", col)]
        df[col.lower()] = (bid + ask) / 2

    if ("last", "Volume") in raw.columns:
        df["volume"] = raw[("last", "Volume")]
    else:
        df["volume"] = 1.0  # repli si IG ne fournit pas de volume pour cet instrument

    df.index.name = "timestamp"
    df.index = pd.to_datetime(df.index)
    return df
