"""
Stratégie hybride : grid trading + filtres multiples + stop-loss/take-profit.
Détection des niveaux basée sur High/Low de la bougie (comme un vrai ordre limite),
pas seulement sur le prix de clôture.
"""
import pandas as pd
import numpy as np

import config


def _compute_atr(df: pd.DataFrame, period: int) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def _compute_atr_percentile(atr: pd.Series, window: int) -> pd.Series:
    return atr.rolling(window).apply(lambda s: (s.iloc[-1] >= s).mean() * 100, raw=False)


def _compute_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _compute_macd(close: pd.Series, fast: int, slow: int, signal: int) -> tuple:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def _compute_htf_trend(df: pd.DataFrame, ma_period: int) -> pd.Series:
    daily_close = df["close"].resample("1D").last()
    daily_ma = daily_close.rolling(ma_period).mean()
    daily_uptrend = pd.Series(np.where(daily_ma.notna(), daily_close > daily_ma, np.nan), index=daily_close.index)
    hourly = daily_uptrend.reindex(df.index, method="ffill")
    return hourly.fillna(True).astype(bool)


def _compute_bollinger(close: pd.Series, period: int, num_std: float) -> tuple:
    """Retourne (bande_basse, bande_haute, largeur_pct) des Bollinger Bands."""
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    lower = sma - num_std * std
    upper = sma + num_std * std
    width_pct = (upper - lower) / sma * 100
    return lower, upper, width_pct


def _compute_alligator(df: pd.DataFrame) -> tuple:
    """
    Indicateur Alligator (Bill Williams) : 3 moyennes mobiles décalées vers l'avant
    sur le prix médian (high+low)/2. Mâchoire (13, décalée +8), Dents (8, décalée +5),
    Lèvres (5, décalée +3). Lignes enchevêtrées = marché "endormi" (range, favorable
    au grid) ; lignes qui s'écartent = marché "réveillé" (tendance, défavorable).
    Ajouté en mode OBSERVATION uniquement — ne bloque aucun trade pour l'instant,
    sert à comparer son signal à HTF/Bollinger sur de vraies données avant de
    décider s'il apporte une information supplémentaire ou fait doublon.
    """
    median_price = (df["high"] + df["low"]) / 2
    jaw = median_price.rolling(13).mean().shift(8)
    teeth = median_price.rolling(8).mean().shift(5)
    lips = median_price.rolling(5).mean().shift(3)
    return jaw, teeth, lips


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["trend_ma"] = df["close"].rolling(config.TREND_MA_PERIOD).mean()
    df["uptrend"] = df["close"] > df["trend_ma"]

    df["atr"] = _compute_atr(df, config.ATR_PERIOD)
    df["atr_spacing_pct"] = (df["atr"] / df["close"] * 100 * config.ATR_GRID_MULTIPLIER).clip(
        lower=config.ATR_MIN_SPACING_PCT
    )
    df["atr_percentile"] = _compute_atr_percentile(df["atr"], config.VOLATILITY_PERCENTILE_WINDOW)

    df["rsi"] = _compute_rsi(df["close"], config.RSI_PERIOD)

    macd_line, signal_line = _compute_macd(df["close"], config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL)
    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_bullish"] = df["macd"] > df["macd_signal"]

    df["volume_ma"] = df["volume"].rolling(config.VOLUME_MA_PERIOD).mean()
    df["volume_ok"] = df["volume"] >= df["volume_ma"] * config.VOLUME_MIN_RATIO

    df["htf_uptrend"] = _compute_htf_trend(df, config.HTF_MA_PERIOD)

    # Bollinger Bands : détecte les phases de range serré (bon pour le grid) vs
    # d'expansion de volatilité (risque de breakout qui laminerait le grid).
    bb_lower, bb_upper, bb_width_pct = _compute_bollinger(
        df["close"], config.BOLLINGER_PERIOD, config.BOLLINGER_STD
    )
    df["bb_lower"] = bb_lower
    df["bb_upper"] = bb_upper
    df["bb_width_pct"] = bb_width_pct
    # Percentile de la largeur actuelle par rapport à son historique récent —
    # une largeur dans le bas du percentile = range serré = terrain favorable au grid.
    df["bb_width_percentile"] = bb_width_pct.rolling(config.BOLLINGER_PERIOD).apply(
        lambda s: (s.iloc[-1] >= s).mean() * 100, raw=False
    )
    df["bb_squeeze"] = df["bb_width_percentile"] <= config.BOLLINGER_SQUEEZE_PERCENTILE

    # Alligator (observation uniquement, ne filtre aucun trade actuellement)
    jaw, teeth, lips = _compute_alligator(df)
    df["alligator_jaw"] = jaw
    df["alligator_teeth"] = teeth
    df["alligator_lips"] = lips
    # Écart entre les 3 lignes en % du prix — plus c'est petit, plus l'alligator
    # "dort" (lignes enchevêtrées = range). Utile pour comparer à HTF/Bollinger plus tard.
    df["alligator_spread_pct"] = (
        (df[["alligator_jaw", "alligator_teeth", "alligator_lips"]].max(axis=1)
         - df[["alligator_jaw", "alligator_teeth", "alligator_lips"]].min(axis=1))
        / df["close"] * 100
    )

    return df


def build_grid(center_price: float, levels: int, spacing_pct: float) -> list:
    grid = []
    for i in range(1, levels + 1):
        grid.append(round(center_price * (1 - spacing_pct / 100 * i), 6))
        grid.append(round(center_price * (1 + spacing_pct / 100 * i), 6))
    grid.append(round(center_price, 6))
    return sorted(grid)


class GridTrendStrategy:
    def __init__(self, center_price: float):
        self.center_price = center_price
        self.open_grid_positions = []

    def recenter(self, new_center_price: float):
        self.center_price = new_center_price

    def _entry_filters_ok(self, row: pd.Series) -> bool:
        trend_ok = (not config.TREND_FILTER_ENABLED) or bool(row.get("uptrend", True))
        htf_ok = (not config.HTF_TREND_ENABLED) or bool(row.get("htf_uptrend", True))
        rsi_ok = (not config.RSI_FILTER_ENABLED) or (row.get("rsi", 50) < config.RSI_OVERBOUGHT)
        macd_ok = (not config.MACD_FILTER_ENABLED) or bool(row.get("macd_bullish", True))
        volume_ok = (not config.VOLUME_FILTER_ENABLED) or bool(row.get("volume_ok", True))
        # Bollinger utilisé comme coupe-circuit (pas comme exigence stricte) : bloque
        # seulement en cas d'expansion nette des bandes (signal de breakout en cours,
        # dangereux pour un grid) — ne réduit pas les opportunités déjà rares en range normal.
        bollinger_ok = True
        if config.BOLLINGER_ENABLED:
            width_pctile = row.get("bb_width_percentile")
            if width_pctile is not None and not pd.isna(width_pctile):
                bollinger_ok = width_pctile < config.BOLLINGER_EXPANSION_HALT_PERCENTILE
        return trend_ok and htf_ok and rsi_ok and macd_ok and volume_ok and bollinger_ok

    def generate_signal(self, row: pd.Series) -> dict:
        price = row["close"]
        candle_high = row.get("high", price)
        candle_low = row.get("low", price)

        if abs(price - self.center_price) / self.center_price * 100 > config.GRID_RECENTER_THRESHOLD_PCT:
            self.center_price = price

        atr_percentile = row.get("atr_percentile", 0)
        volatility_halted = config.VOLATILITY_HALT_ENABLED and atr_percentile >= config.VOLATILITY_HALT_PERCENTILE

        spacing_pct = row.get("atr_spacing_pct", config.GRID_SPACING_PCT)
        if pd.isna(spacing_pct):
            spacing_pct = config.GRID_SPACING_PCT

        grid_levels = build_grid(self.center_price, config.GRID_LEVELS, spacing_pct)
        buy_levels = [lv for lv in grid_levels if lv < self.center_price]

        buy_allowed = self._entry_filters_ok(row) and not volatility_halted

        if buy_allowed:
            already_open_prices = {p["buy_price"] for p in self.open_grid_positions}
            for lv in buy_levels:
                # Comme un vrai ordre limite : se déclenche si le prix a traversé ce niveau
                # PENDANT la bougie (entre son plus bas et son plus haut), pas seulement si
                # la clôture tombe exactement dessus — sinon on rate presque tout.
                if candle_low <= lv <= candle_high and lv not in already_open_prices:
                    self.open_grid_positions.append({"buy_price": lv, "spacing_pct": spacing_pct})
                    return {"action": "BUY", "price": lv, "size_usd": config.GRID_ORDER_SIZE_USD, "grid_level": lv}

        for pos in list(self.open_grid_positions):
            take_profit_price = pos["buy_price"] * (1 + pos["spacing_pct"] / 100)
            stop_loss_price = None
            if config.STOP_LOSS_ENABLED:
                sl_pct = pos["spacing_pct"] / config.STOP_LOSS_RATIO
                stop_loss_price = pos["buy_price"] * (1 - sl_pct / 100)

            if candle_high >= take_profit_price:
                self.open_grid_positions.remove(pos)
                return {"action": "SELL", "price": take_profit_price, "size_usd": config.GRID_ORDER_SIZE_USD,
                        "grid_level": pos["buy_price"], "reason": "take_profit"}

            if stop_loss_price is not None and candle_low <= stop_loss_price:
                self.open_grid_positions.remove(pos)
                return {"action": "SELL", "price": stop_loss_price, "size_usd": config.GRID_ORDER_SIZE_USD,
                        "grid_level": pos["buy_price"], "reason": "stop_loss"}

        return {"action": None, "price": price, "size_usd": 0, "grid_level": None}
