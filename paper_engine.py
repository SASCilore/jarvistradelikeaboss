"""
Moteur de paper trading (argent fictif).
"""
import pandas as pd
import numpy as np

import config


class PaperTradingEngine:
    def __init__(self, starting_balance: float = config.STARTING_BALANCE_USD,
                 fee_rate: float = config.FEE_RATE):
        self.cash = starting_balance
        self.btc_holdings = 0.0
        self.fee_rate = fee_rate
        self.starting_balance = starting_balance
        self.trade_log = []
        self.equity_curve = []

    def _equity(self, price: float) -> float:
        return self.cash + self.btc_holdings * price

    def execute(self, signal: dict, timestamp):
        action = signal["action"]
        price = signal["price"]
        size_usd = signal["size_usd"]

        if action == "BUY" and self.cash >= size_usd:
            fee = size_usd * self.fee_rate
            btc_bought = (size_usd - fee) / price
            self.cash -= size_usd
            self.btc_holdings += btc_bought
            self.trade_log.append({
                "timestamp": timestamp, "action": "BUY", "price": price,
                "size_usd": size_usd, "fee": fee, "btc_amount": btc_bought
            })

        elif action == "SELL" and self.btc_holdings > 0:
            btc_to_sell = min(size_usd / price, self.btc_holdings)
            proceeds = btc_to_sell * price
            fee = proceeds * self.fee_rate
            self.cash += proceeds - fee
            self.btc_holdings -= btc_to_sell
            self.trade_log.append({
                "timestamp": timestamp, "action": "SELL", "price": price,
                "size_usd": proceeds, "fee": fee, "btc_amount": btc_to_sell
            })

    def record_equity(self, timestamp, price: float):
        self.equity_curve.append({"timestamp": timestamp, "equity": self._equity(price)})

    def current_drawdown_pct(self) -> float:
        if not self.equity_curve:
            return 0.0
        equities = [e["equity"] for e in self.equity_curve]
        peak = max(equities)
        current = equities[-1]
        return (peak - current) / peak * 100 if peak > 0 else 0.0

    def report(self) -> dict:
        if not self.equity_curve:
            return {}

        equity_df = pd.DataFrame(self.equity_curve).set_index("timestamp")
        final_equity = equity_df["equity"].iloc[-1]
        total_return_pct = (final_equity - self.starting_balance) / self.starting_balance * 100

        returns = equity_df["equity"].pct_change().dropna()
        sharpe = (returns.mean() / returns.std() * np.sqrt(252 * 24)) if returns.std() > 0 else 0.0

        running_max = equity_df["equity"].cummax()
        drawdown = (equity_df["equity"] - running_max) / running_max * 100
        max_drawdown = drawdown.min()

        n_trades = len(self.trade_log)
        wins = [t for t in self.trade_log if t["action"] == "SELL"]

        return {
            "solde_initial_usd": self.starting_balance,
            "solde_final_usd": round(final_equity, 2),
            "rendement_total_pct": round(total_return_pct, 2),
            "sharpe_ratio_approx": round(sharpe, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "nombre_trades": n_trades,
            "nombre_ventes_realisees": len(wins),
        }

    def export_trades_csv(self, path: str = "results/trades.csv"):
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if self.trade_log:
            pd.DataFrame(self.trade_log).to_csv(path, index=False)
        print(f"Trades exportés dans {path}")

    def export_equity_csv(self, path: str = "results/equity_curve.csv"):
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if self.equity_curve:
            pd.DataFrame(self.equity_curve).to_csv(path, index=False)
        print(f"Courbe d'equity exportée dans {path}")
