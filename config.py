"""
Configuration centrale du bot de trading.
Modifie ces valeurs pour ajuster le comportement sans toucher au reste du code.
"""

# --- Marché ---
EXCHANGE = "kraken"
SYMBOL = "BTC/USD"
TIMEFRAME = "1h"          # granularité des bougies (1m, 5m, 15m, 1h, 4h, 1d...)

# --- Capital simulé (paper trading) ---
STARTING_BALANCE_USD = 10_000.0
FEE_RATE = 0.0026         # taker fee Kraken ~0.26% (à ajuster selon ton tier)

# --- Grid trading ---
GRID_LEVELS = 10          # nombre de niveaux d'achat/vente au-dessus et en dessous du prix central
GRID_SPACING_PCT = 0.5    # espacement de repli si l'ATR n'est pas disponible (warm-up)
GRID_ORDER_SIZE_USD = 200 # taille d'un ordre à chaque niveau
GRID_RECENTER_THRESHOLD_PCT = 5.0  # recentre le grid si le prix s'écarte de plus de X% du centre actuel

# --- ATR : espacement de grid dynamique selon la volatilité réelle ---
ATR_PERIOD = 14
ATR_GRID_MULTIPLIER = 1.0   # espacement du grid = ATR% * ce multiplicateur (plus haut = grid plus large)
ATR_MIN_SPACING_PCT = 0.15  # plancher pour éviter un grid absurdement serré en cas d'ATR très faible

# --- Coupe-circuit volatilité extrême (flash crash / news choc) ---
VOLATILITY_HALT_ENABLED = True
VOLATILITY_PERCENTILE_WINDOW = 720   # fenêtre glissante (en bougies) pour calculer le percentile d'ATR
VOLATILITY_HALT_PERCENTILE = 95      # au-dessus de ce percentile d'ATR historique, le bot arrête d'acheter

# --- RSI : évite d'acheter en zone de surachat ---
RSI_FILTER_ENABLED = True
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70   # pas d'achat si RSI au-dessus de ce seuil

# --- MACD : confirmation de tendance plus réactive que la SMA seule ---
MACD_FILTER_ENABLED = True
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# --- Volume : ne trade que sur des mouvements confirmés par le volume ---
VOLUME_FILTER_ENABLED = True
VOLUME_MA_PERIOD = 20
VOLUME_MIN_RATIO = 1.0   # volume actuel doit être >= VOLUME_MA * ce ratio pour valider un achat

# --- Filtre de tendance ---
TREND_MA_PERIOD = 200     # moyenne mobile utilisée comme filtre de tendance (ex: SMA200)
TREND_FILTER_ENABLED = True

# --- Filtre de tendance multi-timeframe (tendance journalière, indépendante du bruit horaire) ---
HTF_TREND_ENABLED = True
HTF_MA_PERIOD = 50   # moyenne mobile calculée sur les clôtures journalières

# --- Risque ---
MAX_DRAWDOWN_PCT = 20     # coupe-circuit : si le drawdown dépasse ce seuil, le bot s'arrête
