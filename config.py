"""
Configuration centrale du bot de trading.
Modifie ces valeurs pour ajuster le comportement sans toucher au reste du code.
"""

# --- IG (broker forex — remplace Kraken pour l'exécution live) ---
IG_ACC_TYPE = "DEMO"   # "DEMO" ou "LIVE" — on reste en DEMO tant qu'on valide la stratégie
FOREX_EPIC = "CS.D.EURUSD.CEF.IP"   # identifiant IG pour EUR/USD (trouvé via diagnose_ig.py)
# Les identifiants (IG_USERNAME, IG_PASSWORD, IG_API_KEY) se configurent en variables
# d'environnement / secrets GitHub, jamais ici en dur.

# --- Marché ---
EXCHANGE = "kraken"       # exchange utilisé pour l'exécution LIVE (paper puis réel plus tard)
SYMBOL = "BTC/USD"
TIMEFRAME = "15m"         # granularité des bougies (1m, 5m, 15m, 1h, 4h, 1d...)
TIMEFRAME_MINUTES = 15    # doit correspondre à TIMEFRAME — utilisé pour calculer combien
                           # de jours d'historique récupérer selon les périodes ci-dessous

# --- Source de données pour le BACKTEST uniquement (analyse historique) ---
# Kraken limite son API publique à ~720 bougies par requête, peu importe la période
# demandée (~7,5 jours seulement en 15min) — insuffisant pour un vrai backtest.
# Binance a été testé mais bloque les requêtes depuis les serveurs GitHub Actions
# (erreur 451, restriction géographique côté Binance). Coinbase (société américaine,
# pas de blocage depuis les serveurs GitHub) permet une vraie pagination en profondeur.
# Le bot live continue d'utiliser Kraken (EXCHANGE ci-dessus) — seule l'analyse
# historique utilise une source différente, BTC/USD étant très corrélé entre exchanges.
BACKTEST_EXCHANGE = "coinbase"
BACKTEST_SYMBOL = "BTC/USD"

# --- Capital simulé (paper trading) ---
STARTING_BALANCE_USD = 10_000.0
FEE_RATE = 0.0026         # taker fee Kraken ~0.26% (BTC uniquement, ne pas utiliser pour le forex)
FOREX_FEE_RATE = 0.000043 # coût forex (spread IG ~0,0086% aller-retour ÷ 2, car appliqué sur
                           # chaque jambe achat/vente séparément) — 60x moins cher que la crypto

# --- Grid trading (vestiges — le déclencheur "grid à niveaux fixes" a été remplacé
# par le contact avec les Bollinger Bands, mais certains paramètres restent utilisés
# ailleurs : taille d'ordre, nombre de positions simultanées) ---
GRID_LEVELS = 10          # non utilisé par le nouveau déclencheur, gardé pour compat
GRID_SPACING_PCT = 0.5    # espacement de repli si l'ATR n'est pas disponible (warm-up)
GRID_ORDER_SIZE_USD = 200 # taille d'un ordre à chaque niveau
MAX_CONCURRENT_POSITIONS = 5  # nombre max de positions ouvertes simultanément (long + short confondus)
GRID_RECENTER_THRESHOLD_PCT = 1.0  # OBSOLÈTE depuis le passage au déclencheur Bollinger

# --- ATR : espacement dynamique selon la volatilité réelle (= take-profit par position) ---
ATR_PERIOD = 56   # équivalent à 14h en bougies de 15min (14*4)
ATR_GRID_MULTIPLIER = 2.0   # recalibré pour EUR/USD : TP visé ≈ 2x l'ATR réel (~0,036% observé)
ATR_MIN_SPACING_PCT = 0.03  # garde-fou bas (pas le seuil réel) — l'ancien 2,5% était calé sur
                             # le BTC et écrasait complètement la vraie volatilité EUR/USD (~70x trop haut)

# --- Stop-loss par position ---
STOP_LOSS_ENABLED = True
STOP_LOSS_RATIO = 2.5   # recalibré pour EUR/USD : avec TP~0,072% (2xATR) et ratio 2,5,
                          # SL~0,029% ; net après spread IG (~0,0086% aller-retour) ≈ 1,7:1

# --- Coupe-circuit volatilité extrême (flash crash / news choc) ---
VOLATILITY_HALT_ENABLED = True
VOLATILITY_PERCENTILE_WINDOW = 200   # réduit (était 480) pour tenir confortablement dans
                                       # le plafond de 500 points par appel IG
VOLATILITY_HALT_PERCENTILE = 95      # au-dessus de ce percentile d'ATR historique, le bot arrête d'acheter

# --- RSI : évite d'entrer à contre-sens en zone de sur-extension ---
RSI_FILTER_ENABLED = True
RSI_PERIOD = 56   # équivalent à 14h en bougies de 15min
RSI_OVERBOUGHT = 70   # pas d'achat (long) si RSI au-dessus de ce seuil
RSI_OVERSOLD = 30     # pas de vente à découvert (short) si RSI en dessous de ce seuil

# --- MACD : confirmation de tendance plus réactive que la SMA seule ---
MACD_FILTER_ENABLED = False  # désactivé — trop restrictif combiné aux autres filtres
MACD_FAST = 48    # équivalent à 12h
MACD_SLOW = 104   # équivalent à 26h
MACD_SIGNAL = 36  # équivalent à 9h

# --- Volume : ne trade que sur des mouvements confirmés par le volume ---
VOLUME_FILTER_ENABLED = False  # désactivé — trop restrictif pour la fréquence de trades visée
VOLUME_MA_PERIOD = 80   # équivalent à 20h en bougies de 15min
VOLUME_MIN_RATIO = 1.0   # volume actuel doit être >= VOLUME_MA * ce ratio pour valider un achat

# --- Bollinger Bands : déclencheur d'entrée principal (contact bande basse = long,
# bande haute = short) + coupe-circuit sur expansion nette (risque de breakout).
BOLLINGER_ENABLED = True
BOLLINGER_PERIOD = 80    # ~20h en bougies de 15min
BOLLINGER_STD = 1.0      # réduit de 2.0 à 1.0 — à 2x l'écart-type, la bande n'est
                          # touchée que ~5% du temps (quasi aussi rare qu'un grid fixe).
                          # À 1x, ~30% du temps — nécessaire pour une vraie fréquence de trades.
BOLLINGER_SQUEEZE_PERCENTILE = 30  # (informatif, pas encore utilisé dans la logique)
BOLLINGER_EXPANSION_HALT_PERCENTILE = 90  # au-dessus de ce percentile de largeur de
                                            # bande, on considère un breakout en cours
                                            # et on n'ouvre plus de nouvelle position

# --- Alligator (Bill Williams) : filtre actif, plus réactif que la SMA 150 bougies
# pour repérer un début de retournement (bloque long si lèvres<dents, bloque
# short si lèvres>dents).
ALLIGATOR_FILTER_ENABLED = True

# --- ADX (Average Directional Index) : filtre de régime de marché. Sans lui, un
# mean-reversion tombe à ~45% de réussite (échoue en tendance) ; avec lui, 55-65%
# devient réaliste (sources: crosstrade.io, fxnx.com, Bloomberg Intelligence via
# fazencapital.com). Plus réactif que la SMA 150 bougies (basé sur le mouvement
# directionnel récent, pas une moyenne qui accuse un vrai retard).
ADX_FILTER_ENABLED = True
ADX_PERIOD = 14   # période standard de Wilder
ADX_MAX_FOR_ENTRY = 25  # au-dessus, tendance confirmée -> on n'ouvre plus de nouvelle
                         # position mean-reversion (consensus large : <20 range,
                         # 20-25 zone grise, >25 tendance)

# --- Short (vente à découvert) : le forex/CFD permet nativement de trader dans les
# deux sens (pas besoin d'un produit "futures" séparé) — active le short symétrique
# au long, pour trader aussi les phases baissières au lieu de rester inactif.
SHORT_ENABLED = True

# --- Filtre de tendance ---
TREND_MA_PERIOD = 150     # réduit (était 384) pour libérer plus de bougies utilisables sur
                           # les 500 max récupérables par appel IG
TREND_FILTER_ENABLED = True

# --- Filtre de tendance multi-timeframe (tendance journalière, indépendante du bruit horaire) ---
HTF_TREND_ENABLED = True
HTF_MA_PERIOD = 50   # moyenne mobile calculée sur les clôtures journalières

# --- Risque ---
MAX_DRAWDOWN_PCT = 20     # coupe-circuit : si le drawdown dépasse ce seuil, le bot s'arrête
