"""
Backtest sur une semaine spécifique de février 2026 — même stratégie, même
configuration exacte que le bot live (config.py inchangé), seule la source de
données change (période ciblée dans le passé plutôt que "les 500 derniers points").

Usage : python main_forex_february.py
"""
import os
import logging
import pandas as pd

import config
from ig_fetcher import get_ig_service, fetch_ohlcv_ig_date_range
from strategy import add_indicators, GridTrendStrategy
from paper_engine import PaperTradingEngine
from dashboard import generate_dashboard

logging.basicConfig(level=logging.INFO, format="%(message)s")

DATA_PATH = "data/eurusd_february2026.csv"

START_DATE = "2026-02-02 00:00:00"
END_DATE = "2026-02-06 23:45:00"


def load_or_fetch_data() -> pd.DataFrame:
    if os.path.exists(DATA_PATH):
        print(f"Chargement des données depuis {DATA_PATH}")
        return pd.read_csv(DATA_PATH, index_col="timestamp", parse_dates=True)

    print(f"Connexion à IG pour récupérer EUR/USD du {START_DATE} au {END_DATE}...")
    ig_service = get_ig_service()
    df = fetch_ohlcv_ig_date_range(ig_service, config.FOREX_EPIC, resolution="15Min",
                                     start_date=START_DATE, end_date=END_DATE)
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

    print("\n=== Diagnostic des filtres (semaine février 2026) ===")
    print(f"Tendance courte au vert : {trend_ok.mean()*100:.1f}%")
    print(f"Tendance journalière (HTF) au vert : {htf_ok.mean()*100:.1f}%")
    print(f"RSI < {config.RSI_OVERBOUGHT} : {rsi_ok.mean()*100:.1f}%")
    print(f"Pas de coupe-circuit volatilité : {not_halted.mean()*100:.1f}%")
    print(f"--> TOUS les filtres actifs au vert : {all_ok.mean()*100:.2f}% ({all_ok.sum()} / {n})")


def run_backtest():
    df = load_or_fetch_data()
    df = add_indicators(df)
    df_full = df.dropna(subset=["trend_ma"])

    if df_full.empty:
        print("Pas assez de données après calcul des indicateurs.")
        return

    print(f"\nPériode réellement couverte : {df_full.index.min()} -> {df_full.index.max()}")
    print(f"Bougies utilisables : {len(df_full)}")
    print(f"Amplitude de la semaine : {(df_full['close'].max()/df_full['close'].min()-1)*100:.2f}%")

    diagnose_filters(df_full)

    center_price = df_full["close"].iloc[0]
    strat = GridTrendStrategy(center_price)
    engine = PaperTradingEngine(fee_rate=config.FOREX_FEE_RATE)
    tp_count, sl_count = 0, 0

    for timestamp, row in df_full.iterrows():
        signal = strat.generate_signal(row)
        if signal["action"] == "SELL":
            if signal.get("reason") == "take_profit":
                tp_count += 1
            elif signal.get("reason") == "stop_loss":
                sl_count += 1
        if signal["action"]:
            engine.execute(signal, timestamp)
        engine.record_equity(timestamp, row["close"])

        if engine.current_drawdown_pct() > config.MAX_DRAWDOWN_PCT:
            print(f"⚠️  Coupe-circuit déclenché à {timestamp}")
            break

    report = engine.report()
    print("\n=== Résultats — semaine de février 2026 (paper trading) ===")
    for k, v in report.items():
        print(f"{k}: {v}")
    print(f"Take-profits : {tp_count} | Stop-loss : {sl_count}")
    if (tp_count + sl_count) > 0:
        print(f"Win rate : {tp_count/(tp_count+sl_count)*100:.1f}%")

    engine.export_trades_csv(path="results/trades_february.csv")
    engine.export_equity_csv(path="results/equity_february.csv")
    generate_dashboard(df_full, engine, output_path="results/dashboard_february.png")

    return report, engine


if __name__ == "__main__":
    run_backtest()
