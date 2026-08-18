"""
Point d'entrée principal : lance un backtest en paper trading.
Usage: python main.py
"""
import os
import pandas as pd

import config
from data_fetcher import fetch_ohlcv, save_to_csv
from strategy import add_indicators, GridTrendStrategy
from paper_engine import PaperTradingEngine
from dashboard import generate_dashboard


DATA_PATH = "data/btc_usd_history.csv"


def load_or_fetch_data() -> pd.DataFrame:
    if os.path.exists(DATA_PATH):
        print(f"Chargement des données depuis {DATA_PATH}")
        df = pd.read_csv(DATA_PATH, index_col="timestamp", parse_dates=True)
    else:
        df = fetch_ohlcv(symbol=config.BACKTEST_SYMBOL, since_days=365, exchange_id=config.BACKTEST_EXCHANGE)
        save_to_csv(df, DATA_PATH)
    return df


def diagnose_filters(df: pd.DataFrame):
    """
    Affiche, sur l'ensemble de la période, le % de bougies où chaque filtre est au vert
    individuellement, et le % où TOUS les filtres sont au vert en même temps.
    Permet d'identifier lequel est le vrai goulot d'étranglement.
    """
    n = len(df)
    trend_ok = df["uptrend"] if config.TREND_FILTER_ENABLED else pd.Series(True, index=df.index)
    htf_ok = df["htf_uptrend"] if config.HTF_TREND_ENABLED else pd.Series(True, index=df.index)
    rsi_ok = (df["rsi"] < config.RSI_OVERBOUGHT) if config.RSI_FILTER_ENABLED else pd.Series(True, index=df.index)
    macd_ok = df["macd_bullish"] if config.MACD_FILTER_ENABLED else pd.Series(True, index=df.index)
    volume_ok = df["volume_ok"] if config.VOLUME_FILTER_ENABLED else pd.Series(True, index=df.index)
    not_halted = ~(config.VOLATILITY_HALT_ENABLED & (df["atr_percentile"] >= config.VOLATILITY_HALT_PERCENTILE))

    all_ok = trend_ok & htf_ok & rsi_ok & macd_ok & volume_ok & not_halted

    print("\n=== Diagnostic des filtres (sur toute la période) ===")
    print(f"Tendance courte (SMA{config.TREND_MA_PERIOD}) au vert : {trend_ok.mean()*100:.1f}%")
    print(f"Tendance journalière (HTF) au vert : {htf_ok.mean()*100:.1f}%")
    print(f"RSI < {config.RSI_OVERBOUGHT} : {rsi_ok.mean()*100:.1f}%")
    print(f"MACD haussier : {macd_ok.mean()*100:.1f}%")
    print(f"Volume suffisant : {volume_ok.mean()*100:.1f}%")
    print(f"Pas de coupe-circuit volatilité : {not_halted.mean()*100:.1f}%")
    print(f"--> TOUS les filtres au vert en même temps : {all_ok.mean()*100:.2f}% des bougies ({all_ok.sum()} / {n})")


def run_backtest():
    df = load_or_fetch_data()
    df = add_indicators(df)
    df = df.dropna(subset=["trend_ma"])

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
            print(f"⚠️  Coupe-circuit déclenché à {timestamp} (drawdown > {config.MAX_DRAWDOWN_PCT}%)")
            break

    report = engine.report()
    print("\n=== Résultats du backtest (paper trading) ===")
    for k, v in report.items():
        print(f"{k}: {v}")

    engine.export_trades_csv()
    engine.export_equity_csv()
    generate_dashboard(df, engine)

    return report, engine


if __name__ == "__main__":
    run_backtest()
