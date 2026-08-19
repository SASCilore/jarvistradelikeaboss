"""
Script de diagnostic : vérifie que la connexion à IG fonctionne, cherche l'epic
EUR/USD exact, affiche le prix actuel, et teste la récupération de bougies OHLCV.
"""
import config
from ig_fetcher import get_ig_service, find_epic, fetch_current_price, fetch_ohlcv_ig

print("Connexion à IG...")
ig_service = get_ig_service()
print("Connexion réussie !\n")

print("Recherche de l'epic EUR/USD...")
results = find_epic(ig_service, "EURUSD")

print("\nTest de récupération du prix actuel sur le premier résultat...")
if len(results) > 0:
    first_epic = results.iloc[0]["epic"]
    price = fetch_current_price(ig_service, first_epic)
    print(f"Epic testé : {first_epic}")
    print(f"Prix actuel : bid={price['bid']}, offer={price['offer']}, mid={price['mid']}")

    print(f"\nTest de récupération de bougies OHLCV (15 dernières bougies 15min)...")
    df = fetch_ohlcv_ig(ig_service, first_epic, resolution="15Min", num_points=15)
    print(df.tail(10))
    print(f"\nColonnes: {list(df.columns)}")
    print(f"Nombre de lignes: {len(df)}")
else:
    print("Aucun résultat trouvé pour 'EURUSD'.")
