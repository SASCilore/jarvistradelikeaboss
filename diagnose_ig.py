"""
Script de diagnostic : vérifie que la connexion à IG fonctionne, cherche l'epic
EUR/USD exact, et affiche le prix actuel.
"""
from ig_fetcher import get_ig_service, find_epic, fetch_current_price

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
else:
    print("Aucun résultat trouvé pour 'EURUSD'.")
