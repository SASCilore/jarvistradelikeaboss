"""
Backtest forex (EUR/USD via IG) — réutilise la même stratégie, le même moteur de
paper trading et le même dashboard que le bot BTC (strategy.py, paper_engine.py,
dashboard.py sont génériques, indépendants de l'actif tradé).

Usage : python main_forex.py
"""
import os
import logging
import pandas as pd

import config
from ig_fetcher import get_ig_service, fetch_ohlcv_ig
from strategy import add_indicators, GridTrendStrategy
from paper_engine import PaperTradingEngine
from dashboard import generate_dashboard

# Affiche les logs internes de la librairie trading_ig, notamment le quota
# restant de données historiques ("Historic price data allowance: X remaining")
logging.basicConfig(level=logging.INFO, format="%(message)s")

DATA_PATH = "data/eurusd_history.csv"


def load_or_fetch_data() -> pd.DataFrame:
    if os.path.exists(DATA_PATH):
        print(f"Chargement des données depuis {DATA_PATH}")
        return pd.read_csv(DATA_PATH, index_col="timestamp", parse_dates=True)

    print("Connexion à IG pour récupérer l'historique EUR/USD...")
    ig_service = get_ig_service()
    # Quota vérifié : ~9225/10000 restants cette semaine, largement de quoi
    # récupérer 1000 points (nécessaire pour couvrir les fenêtres des indicateurs).
    df = fetch_ohlcv_ig(ig_service, config.FOREX_EPIC, resolution="15Min", num_points=1000)
    os.makedirs("data", exist_ok=True)
    df.to_csv(DATA_PATH)
    print(f"-> {len(df)} bougies récupérées et sauvegardées.")
    return df


def diagnose_filters(df: pd.DataFrame):
    n = len(df)
    trend_ok = df["uptrend"] if config.TREND_FILTER_ENABLED else pd.Series(True, index=df.index)
    htf_ok = df["htf_uptrend"] if config.HTF_TREND_ENABLED else pd.Series(True, index=df.index)
    rsi_ok = (df["rsi"] < config.RSI_OVERBOUGHT) if config.RSI_FILTER_ENABLED else pd.Series(True, index=df.index)
    macd_ok = df["macd_bullish"] if config.MACD_FILTER_ENABLED else pd.Series(True, index=df.index)
    volume_ok = df["volume_ok"] if config.VOLUME_FILTER_ENABLED else pd.Series(True, index=df.index)
    not_halted = ~(config.VOLATILITY_HALT_ENABLED & (df["atr_percentile"] >= config.VOLATILITY_HALT_PERCENTILE))
    all_ok = trend_ok & htf_ok & rsi_ok & macd_ok & volume_ok & not_halted

    print("\n=== Diagnostic des filtres ===")
    print(f"Tendance courte au vert : {trend_ok.mean()*100:.1f}%")
    print(f"Tendance journalière (HTF) au vert : {htf_ok.mean()*100:.1f}%")
    print(f"RSI < {config.RSI_OVERBOUGHT} : {rsi_ok.mean()*100:.1f}%")
    print(f"MACD haussier : {macd_ok.mean()*100:.1f}%")
    print(f"Volume suffisant : {volume_ok.mean()*100:.1f}%")
    print(f"Pas de coupe-circuit volatilité : {not_halted.mean()*100:.1f}%")
    print(f"--> TOUS les filtres au vert : {all_ok.mean()*100:.2f}% ({all_ok.sum()} / {n})")


def diagnose_volatility(df: pd.DataFrame):
    """Affiche la volatilité réelle observée pour calibrer les seuils TP/SL sur EUR/USD."""
    print("\n=== Diagnostic de volatilité (pour calibration TP/SL) ===")
    print(f"ATR moyen (en % du prix) : {(df['atr'] / df['close'] * 100).mean():.4f}%")
    print(f"Espacement de grid calculé (atr_spacing_pct) — moyenne : {df['atr_spacing_pct'].mean():.4f}%")
    print(f"Mouvement max sur une bougie (high-low, % du close) : {((df['high']-df['low'])/df['close']*100).max():.4f}%")
    print(f"Amplitude totale de la période (min-max close) : {((df['close'].max()-df['close'].min())/df['close'].min()*100):.2f}%")


def run_backtest():
    df = load_or_fetch_data()
    df = add_indicators(df)
    df = df.dropna(subset=["trend_ma"])

    if df.empty:
        print("Pas assez de données après calcul des indicateurs — réduis les périodes dans config.py.")
        return

    diagnose_volatility(df)
    diagnose_filters(df)

    center_price = df["close"].iloc[0]
    strat = GridTrendStrategy(center_price)
    engine = PaperTradingEngine()

    for timestamp, row in df.iterrows():
        signal = strat.generate_signal(row)
        if signal["action"]:
            engine.execute(signal, timestamp)
        engine.record_equity(timestamp, row["close"])

        if engine.current_drawdown_pct() > config.MAX_DRAWDOWN_PCT:
            print(f"⚠️  Coupe-circuit déclenché à {timestamp}")
            break

    report = engine.report()
    print("\n=== Résultats du backtest EUR/USD (paper trading) ===")
    for k, v in report.items():
        print(f"{k}: {v}")

    engine.export_trades_csv(path="results/trades_forex.csv")
    engine.export_equity_csv(path="results/equity_curve_forex.csv")
    generate_dashboard(df, engine, output_path="results/dashboard_forex.png")

    return report, engine


if __name__ == "__main__":
    run_backtest()
