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
        # Backtest sur Binance (historique profond disponible), exécution live reste sur Kraken.
        df = fetch_ohlcv(symbol=config.BACKTEST_SYMBOL, since_days=365, exchange_id=config.BACKTEST_EXCHANGE)
        save_to_csv(df, DATA_PATH)
    return df


def run_backtest():
    df = load_or_fetch_data()
    df = add_indicators(df)
    df = df.dropna(subset=["trend_ma"])

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
