"""
Recherche les instruments disponibles sur IG parmi les candidats plus volatils
que le forex : crypto (BTC), or (Gold), indices (Nasdaq, Dow/Wall Street).
Ne consomme quasiment pas le quota (search_markets est un appel léger, séparé
du quota de données historiques).
"""
from ig_fetcher import get_ig_service, find_epic, fetch_current_price

print("Connexion à IG...")
ig_service = get_ig_service()
print("Connexion réussie !\n")

search_terms = ["Bitcoin", "Gold", "US Tech 100", "Wall Street", "Dow Jones"]

for term in search_terms:
    print(f"\n{'='*50}")
    print(f"Recherche : '{term}'")
    print('='*50)
    try:
        results = find_epic(ig_service, term)
        if len(results) > 0:
            first_epic = results.iloc[0]["epic"]
            try:
                price = fetch_current_price(ig_service, first_epic)
                print(f"  -> Prix actuel du 1er résultat ({first_epic}): "
                      f"bid={price['bid']}, offer={price['offer']}")
            except Exception as e:
                print(f"  -> Impossible de récupérer le prix : {e}")
    except Exception as e:
        print(f"Erreur lors de la recherche de '{term}': {e}")

print("\n\nRecherche terminée.")
