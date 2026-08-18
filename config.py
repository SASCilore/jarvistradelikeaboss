"""
Configuration centrale du bot de trading.
Modifie ces valeurs pour ajuster le comportement sans toucher au reste du code.
"""

# --- Marché ---
EXCHANGE = "kraken"
SYMBOL = "BTC/USD"
TIMEFRAME = "15m"         # granularité des bougies (1m, 5m, 15m, 1h, 4h, 1d...)
TIMEFRAME_MINUTES = 15    # doit correspondre à TIMEFRAME — utilisé pour calculer combien
                           # de jours d'historique récupérer selon les périodes ci-dessous

# --- Capital simulé (paper trading) ---
STARTING_BALANCE_USD = 10_000.0
FEE_RATE = 0.0026         # taker fee Kraken ~0.26% (à ajuster selon ton tier)

# --- Grid trading ---
GRID_LEVELS = 10          # nombre de niveaux d'achat/vente au-dessus et en dessous du prix central
GRID_SPACING_PCT = 0.5    # espacement de repli si l'ATR n'est pas disponible (warm-up)
GRID_ORDER_SIZE_USD = 200 # taille d'un ordre à chaque niveau
GRID_RECENTER_THRESHOLD_PCT = 5.0  # recentre le grid si le prix s'écarte de plus de X% du centre actuel

# --- ATR : espacement de grid dynamique selon la volatilité réelle (= take-profit par position) ---
ATR_PERIOD = 56   # équivalent à 14h en bougies de 15min (14*4)
ATR_GRID_MULTIPLIER = 1.0   # espacement du grid = ATR% * ce multiplicateur (plus haut = grid plus large)
ATR_MIN_SPACING_PCT = 2.5   # plancher du take-profit — calibré pour un ratio 3:1 brut avec
                             # le stop-loss (~1,46:1 net après frais), en gardant des trades
                             # raisonnablement fréquents (mouvements de 2,5% pas rares sur BTC)

# --- Stop-loss par position ---
STOP_LOSS_ENABLED = True
STOP_LOSS_RATIO = 3.0   # le stop-loss = take-profit / ce ratio → avec TP~2,5% et ratio 3,
                          # SL~0,83% ; ratio brut 3:1, net après frais (~0,52% aller-retour) ≈ 1,46:1
                          # Seuil de rentabilité (win rate minimum) avec ces chiffres : ~40,5%

# --- Coupe-circuit volatilité extrême (flash crash / news choc) ---
VOLATILITY_HALT_ENABLED = True
VOLATILITY_PERCENTILE_WINDOW = 480   # ~5 jours en bougies de 15min — réduit pour tenir
                                       # confortablement dans les limites de récupération de Kraken
VOLATILITY_HALT_PERCENTILE = 95      # au-dessus de ce percentile d'ATR historique, le bot arrête d'acheter

# --- RSI : évite d'acheter en zone de surachat ---
RSI_FILTER_ENABLED = True
RSI_PERIOD = 56   # équivalent à 14h en bougies de 15min
RSI_OVERBOUGHT = 70   # pas d'achat si RSI au-dessus de ce seuil

# --- MACD : confirmation de tendance plus réactive que la SMA seule ---
MACD_FILTER_ENABLED = True
MACD_FAST = 48    # équivalent à 12h
MACD_SLOW = 104   # équivalent à 26h
MACD_SIGNAL = 36  # équivalent à 9h

# --- Volume : ne trade que sur des mouvements confirmés par le volume ---
VOLUME_FILTER_ENABLED = True
VOLUME_MA_PERIOD = 80   # équivalent à 20h en bougies de 15min
VOLUME_MIN_RATIO = 1.0   # volume actuel doit être >= VOLUME_MA * ce ratio pour valider un achat

# --- Filtre de tendance ---
TREND_MA_PERIOD = 384     # ~4 jours (96h) en bougies de 15min — réduit pour tenir avec marge
TREND_FILTER_ENABLED = True

# --- Filtre de tendance multi-timeframe (tendance journalière, indépendante du bruit horaire) ---
HTF_TREND_ENABLED = True
HTF_MA_PERIOD = 50   # moyenne mobile calculée sur les clôtures journalières

# --- Risque ---
MAX_DRAWDOWN_PCT = 20     # coupe-circuit : si le drawdown dépasse ce seuil, le bot s'arrête
