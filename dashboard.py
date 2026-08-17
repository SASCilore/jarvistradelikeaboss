"""
Génère un tableau de bord visuel PNG à partir des résultats d'un backtest.
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_dashboard(price_df: pd.DataFrame, engine, output_path: str = "results/dashboard.png"):
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    trades_df = pd.DataFrame(engine.trade_log)
    equity_df = pd.DataFrame(engine.equity_curve)

    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=False,
                              gridspec_kw={"height_ratios": [2, 1, 1]})

    ax1 = axes[0]
    ax1.plot(price_df.index, price_df["close"], color="#4a5568", linewidth=0.8, label="Prix BTC/USD")

    if not trades_df.empty:
        trades_df["timestamp"] = pd.to_datetime(trades_df["timestamp"])
        buys = trades_df[trades_df["action"] == "BUY"]
        sells = trades_df[trades_df["action"] == "SELL"]
        ax1.scatter(buys["timestamp"], buys["price"], color="#2f855a", marker="^", s=60, label="Achat", zorder=5)
        ax1.scatter(sells["timestamp"], sells["price"], color="#c53030", marker="v", s=60, label="Vente", zorder=5)

    ax1.set_title("Prix BTC/USD et points d'exécution du bot", fontsize=13, fontweight="bold")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.3)

    ax2 = axes[1]
    if not equity_df.empty:
        equity_df["timestamp"] = pd.to_datetime(equity_df["timestamp"])
        ax2.plot(equity_df["timestamp"], equity_df["equity"], color="#2b6cb0", linewidth=1.2)
        ax2.axhline(equity_df["equity"].iloc[0], color="gray", linestyle="--", linewidth=0.8, label="Capital de départ")
    ax2.set_title("Évolution du portefeuille (equity curve)", fontsize=13, fontweight="bold")
    ax2.legend(loc="upper left")
    ax2.grid(alpha=0.3)

    ax3 = axes[2]
    if not equity_df.empty:
        running_max = equity_df["equity"].cummax()
        drawdown = (equity_df["equity"] - running_max) / running_max * 100
        ax3.fill_between(equity_df["timestamp"], drawdown, 0, color="#c53030", alpha=0.4)
        ax3.plot(equity_df["timestamp"], drawdown, color="#c53030", linewidth=0.8)
    ax3.set_title("Drawdown (%)", fontsize=13, fontweight="bold")
    ax3.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=130)
    plt.close(fig)
    print(f"Dashboard visuel généré : {output_path}")
