"""
Stratégie hybride : grid trading + filtres multiples.

Indicateurs utilisés :
- ATR       -> espacement du grid dynamique selon la volatilité réelle du marché
- Percentile ATR -> coupe-circuit en cas de volatilité extrême (flash crash, news choc)
- RSI       -> évite d'acheter en zone de surachat
- MACD      -> confirme que la tendance de fond est haussière avant d'acheter
- Volume    -> ne valide un achat que si le mouvement est confirmé par le volume
- SMA200    -> filtre de tendance de base (même timeframe que le trading)
- SMA50 journalière -> filtre de tendance multi-timeframe (indépendant du bruit horaire)
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
    """Percentile (0-100) de la valeur ATR actuelle par rapport à sa fenêtre glissante récente."""
    return atr.rolling(window).apply(lambda s: (s.iloc[-1] >= s).mean() * 100, raw=False)


def _compute_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)  # neutre si pas assez de données/pas de perte


def _compute_macd(close: pd.Series, fast: int, slow: int, signal: int) -> tuple:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def _compute_htf_trend(df: pd.DataFrame, ma_period: int) -> pd.Series:
    """Tendance sur clôtures journalières, reportée (forward-fill) sur l'index horaire d'origine."""
    daily_close = df["close"].resample("1D").last()
    daily_ma = daily_close.rolling(ma_period).mean()
    daily_uptrend = pd.Series(np.where(daily_ma.notna(), daily_close > daily_ma, np.nan), index=daily_close.index)
    hourly = daily_uptrend.reindex(df.index, method="ffill")
    return hourly.fillna(True).astype(bool)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule tous les indicateurs utilisés par la stratégie et les ajoute au DataFrame."""
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

    return df


def build_grid(center_price: float, levels: int, spacing_pct: float) -> list:
    """Construit les niveaux de prix du grid autour d'un prix central, pour un espacement donné."""
    grid = []
    for i in range(1, levels + 1):
        grid.append(round(center_price * (1 - spacing_pct / 100 * i), 2))
        grid.append(round(center_price * (1 + spacing_pct / 100 * i), 2))
    grid.append(round(center_price, 2))
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
        return trend_ok and htf_ok and rsi_ok and macd_ok and volume_ok

    def generate_signal(self, row: pd.Series) -> dict:
        price = row["close"]

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
                if abs(price - lv) / lv < 0.001 and lv not in already_open_prices:
                    self.open_grid_positions.append({"buy_price": lv, "spacing_pct": spacing_pct})
                    return {"action": "BUY", "price": price, "size_usd": config.GRID_ORDER_SIZE_USD, "grid_level": lv}

        for pos in list(self.open_grid_positions):
            target_sell = pos["buy_price"] * (1 + pos["spacing_pct"] / 100)
            if price >= target_sell:
                self.open_grid_positions.remove(pos)
                return {"action": "SELL", "price": price, "size_usd": config.GRID_ORDER_SIZE_USD, "grid_level": pos["buy_price"]}

        return {"action": None, "price": price, "size_usd": 0, "grid_level": None}
