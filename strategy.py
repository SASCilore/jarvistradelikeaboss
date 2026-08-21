"""
Stratégie mean-reversion : achat sur contact avec la bande basse des Bollinger,
filtrée par un régime de marché (ADX) pour éviter d'acheter des creux pendant
une vraie tendance, plus RSI/HTF/Alligator comme filtres complémentaires.
Stop-loss/take-profit basés sur l'ATR.
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
    sur le prix médian (high+low)/2. Bloque l'achat si les lèvres (rapide) passent
    sous les dents (moyenne) — signal précoce de retournement baissier.
    """
    median_price = (df["high"] + df["low"]) / 2
    jaw = median_price.rolling(13).mean().shift(8)
    teeth = median_price.rolling(8).mean().shift(5)
    lips = median_price.rolling(5).mean().shift(3)
    return jaw, teeth, lips


def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    ADX (Average Directional Index, Wilder) : mesure la FORCE d'une tendance,
    indépendamment de sa direction. Contrairement à une moyenne mobile (qui accuse
    un vrai retard), l'ADX se base sur le mouvement directionnel des bougies
    récentes — beaucoup plus réactif pour détecter un début de tendance.
    ADX < 20-25 = marché en range (favorable au mean-reversion).
    ADX > 25 = tendance confirmée (dangereux pour l'achat de creux).
    """
    high, low, close = df["high"], df["low"], df["close"]

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    high_low = high - low
    high_close = (high - close.shift()).abs()
    low_close = (low - close.shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    atr_wilder = true_range.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_wilder
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_wilder

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx.fillna(0)


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

    bb_lower, bb_upper, bb_width_pct = _compute_bollinger(
        df["close"], config.BOLLINGER_PERIOD, config.BOLLINGER_STD
    )
    df["bb_lower"] = bb_lower
    df["bb_upper"] = bb_upper
    df["bb_width_pct"] = bb_width_pct
    df["bb_width_percentile"] = bb_width_pct.rolling(config.BOLLINGER_PERIOD).apply(
        lambda s: (s.iloc[-1] >= s).mean() * 100, raw=False
    )
    df["bb_squeeze"] = df["bb_width_percentile"] <= config.BOLLINGER_SQUEEZE_PERCENTILE

    jaw, teeth, lips = _compute_alligator(df)
    df["alligator_jaw"] = jaw
    df["alligator_teeth"] = teeth
    df["alligator_lips"] = lips
    df["alligator_spread_pct"] = (
        (df[["alligator_jaw", "alligator_teeth", "alligator_lips"]].max(axis=1)
         - df[["alligator_jaw", "alligator_teeth", "alligator_lips"]].min(axis=1))
        / df["close"] * 100
    )

    df["adx"] = _compute_adx(df, config.ADX_PERIOD)

    return df


def build_grid(center_price: float, levels: int, spacing_pct: float) -> list:
    """Conservé pour compatibilité (utilisé par certains scripts de diagnostic),
    mais n'est plus utilisé par GridTrendStrategy pour générer des signaux."""
    grid = []
    for i in range(1, levels + 1):
        grid.append(round(center_price * (1 - spacing_pct / 100 * i), 6))
        grid.append(round(center_price * (1 + spacing_pct / 100 * i), 6))
    grid.append(round(center_price, 6))
    return sorted(grid)


class GridTrendStrategy:
    """
    Stratégie mean-reversion BIDIRECTIONNELLE : achat sur contact avec la bande
    basse des Bollinger (long), vente à découvert sur contact avec la bande haute
    (short) — permet de trader aussi bien les phases de range que les faux départs
    de tendance dans les deux sens, plutôt que de rester inactif pendant les baisses.
    """
    def __init__(self, center_price: float):
        self.center_price = center_price
        self.open_grid_positions = []  # chaque position a un champ "direction": "long"/"short"

    def recenter(self, new_center_price: float):
        self.center_price = new_center_price

    def _regime_filters_ok(self, row: pd.Series) -> bool:
        """Filtres partagés entre long et short : coupe-circuit expansion des
        bandes (Bollinger) et régime de marché (ADX) — s'appliquent pareil
        quelle que soit la direction envisagée."""
        bollinger_ok = True
        if config.BOLLINGER_ENABLED:
            width_pctile = row.get("bb_width_percentile")
            if width_pctile is not None and not pd.isna(width_pctile):
                bollinger_ok = width_pctile < config.BOLLINGER_EXPANSION_HALT_PERCENTILE
        adx_ok = True
        if config.ADX_FILTER_ENABLED:
            adx = row.get("adx")
            if adx is not None and not pd.isna(adx):
                adx_ok = adx < config.ADX_MAX_FOR_ENTRY
        return bollinger_ok and adx_ok

    def _directional_filters_ok(self, row: pd.Series, direction: str) -> bool:
        """Filtres spécifiques à la direction envisagée (long ou short) —
        symétriques : ce qui confirme un achat pour le long doit être inversé
        pour le short (ex: éviter d'acheter en tendance baissière naissante,
        éviter de vendre à découvert en tendance haussière naissante)."""
        uptrend = bool(row.get("uptrend", True))
        htf_uptrend = bool(row.get("htf_uptrend", True))
        rsi = row.get("rsi", 50)
        macd_bullish = bool(row.get("macd_bullish", True))
        lips = row.get("alligator_lips")
        teeth = row.get("alligator_teeth")
        volume_ok = bool(row.get("volume_ok", True))

        if direction == "long":
            trend_ok = (not config.TREND_FILTER_ENABLED) or uptrend
            htf_ok = (not config.HTF_TREND_ENABLED) or htf_uptrend
            rsi_ok = (not config.RSI_FILTER_ENABLED) or (rsi < config.RSI_OVERBOUGHT)
            macd_ok = (not config.MACD_FILTER_ENABLED) or macd_bullish
            alligator_ok = True
            if config.ALLIGATOR_FILTER_ENABLED and lips is not None and teeth is not None \
                    and not pd.isna(lips) and not pd.isna(teeth):
                alligator_ok = lips >= teeth
        else:  # short
            trend_ok = (not config.TREND_FILTER_ENABLED) or (not uptrend)
            htf_ok = (not config.HTF_TREND_ENABLED) or (not htf_uptrend)
            rsi_ok = (not config.RSI_FILTER_ENABLED) or (rsi > config.RSI_OVERSOLD)
            macd_ok = (not config.MACD_FILTER_ENABLED) or (not macd_bullish)
            alligator_ok = True
            if config.ALLIGATOR_FILTER_ENABLED and lips is not None and teeth is not None \
                    and not pd.isna(lips) and not pd.isna(teeth):
                alligator_ok = lips <= teeth

        volume_condition = (not config.VOLUME_FILTER_ENABLED) or volume_ok
        return trend_ok and htf_ok and rsi_ok and macd_ok and alligator_ok and volume_condition

    def generate_signal(self, row: pd.Series) -> dict:
        price = row["close"]
        candle_high = row.get("high", price)
        candle_low = row.get("low", price)

        atr_percentile = row.get("atr_percentile", 0)
        volatility_halted = config.VOLATILITY_HALT_ENABLED and atr_percentile >= config.VOLATILITY_HALT_PERCENTILE

        spacing_pct = row.get("atr_spacing_pct", config.GRID_SPACING_PCT)
        if pd.isna(spacing_pct):
            spacing_pct = config.GRID_SPACING_PCT

        regime_ok = self._regime_filters_ok(row) and not volatility_halted

        if regime_ok and len(self.open_grid_positions) < config.MAX_CONCURRENT_POSITIONS:
            bb_lower = row.get("bb_lower")
            bb_upper = row.get("bb_upper")

            # Entrée LONG : contact avec la bande basse
            if (self._directional_filters_ok(row, "long") and bb_lower is not None
                    and not pd.isna(bb_lower) and candle_low <= bb_lower <= candle_high):
                self.open_grid_positions.append({"buy_price": bb_lower, "spacing_pct": spacing_pct, "direction": "long"})
                return {"action": "BUY", "price": bb_lower, "size_usd": config.GRID_ORDER_SIZE_USD,
                        "grid_level": bb_lower, "direction": "long"}

            # Entrée SHORT : contact avec la bande haute
            if (config.SHORT_ENABLED and self._directional_filters_ok(row, "short") and bb_upper is not None
                    and not pd.isna(bb_upper) and candle_low <= bb_upper <= candle_high):
                self.open_grid_positions.append({"buy_price": bb_upper, "spacing_pct": spacing_pct, "direction": "short"})
                return {"action": "SELL", "price": bb_upper, "size_usd": config.GRID_ORDER_SIZE_USD,
                        "grid_level": bb_upper, "direction": "short"}

        # Sorties : take-profit / stop-loss, inversés selon la direction de la position
        for pos in list(self.open_grid_positions):
            entry = pos["buy_price"]
            sp = pos["spacing_pct"]
            sl_pct = sp / config.STOP_LOSS_RATIO if config.STOP_LOSS_ENABLED else None

            if pos["direction"] == "long":
                take_profit_price = entry * (1 + sp / 100)
                stop_loss_price = entry * (1 - sl_pct / 100) if sl_pct is not None else None

                if candle_high >= take_profit_price:
                    self.open_grid_positions.remove(pos)
                    return {"action": "SELL", "price": take_profit_price, "size_usd": config.GRID_ORDER_SIZE_USD,
                            "grid_level": entry, "reason": "take_profit", "direction": "long"}
                if stop_loss_price is not None and candle_low <= stop_loss_price:
                    self.open_grid_positions.remove(pos)
                    return {"action": "SELL", "price": stop_loss_price, "size_usd": config.GRID_ORDER_SIZE_USD,
                            "grid_level": entry, "reason": "stop_loss", "direction": "long"}

            else:  # short : le profit vient d'une BAISSE du prix après l'entrée
                take_profit_price = entry * (1 - sp / 100)
                stop_loss_price = entry * (1 + sl_pct / 100) if sl_pct is not None else None

                if candle_low <= take_profit_price:
                    self.open_grid_positions.remove(pos)
                    return {"action": "BUY", "price": take_profit_price, "size_usd": config.GRID_ORDER_SIZE_USD,
                            "grid_level": entry, "reason": "take_profit", "direction": "short"}
                if stop_loss_price is not None and candle_high >= stop_loss_price:
                    self.open_grid_positions.remove(pos)
                    return {"action": "BUY", "price": stop_loss_price, "size_usd": config.GRID_ORDER_SIZE_USD,
                            "grid_level": entry, "reason": "stop_loss", "direction": "short"}

        return {"action": None, "price": price, "size_usd": 0, "grid_level": None}
