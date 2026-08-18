"""
Génère un dashboard visuel à partir des données RÉELLES accumulées par le bot.
Usage (en local) : python view_live_performance.py
"""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

EQUITY_PATH = "state/equity_history.csv"
TRADES_PATH = "state/trades_history.csv"
OUTPUT_PATH = "results/live_dashboard.png"


def main():
    if not os.path.exists(EQUITY_PATH):
        print(f"Aucune donnée trouvée dans {EQUITY_PATH} pour l'instant.")
        print("Le bot doit avoir tourné au moins une fois en autonomie pour générer ce fichier.")
        return

    equity_df = pd.read_csv(EQUITY_PATH, parse_dates=["timestamp"])
    trades_df = pd.read_csv(TRADES_PATH, parse_dates=["timestamp"]) if os.path.exists(TRADES_PATH) else pd.DataFrame()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [2, 1]})

    ax1 = axes[0]
    ax1.plot(equity_df["timestamp"], equity_df["equity"], color="#2b6cb0", linewidth=1.5, label="Valeur du portefeuille")
    ax1.axhline(equity_df["equity"].iloc[0], color="gray", linestyle="--", linewidth=0.8, label="Capital de départ")

    if not trades_df.empty:
        buys = trades_df[trades_df["action"] == "BUY"]
        sells = trades_df[trades_df["action"] == "SELL"]
        for _, t in buys.iterrows():
            ax1.axvline(t["timestamp"], color="#2f855a", alpha=0.2, linewidth=1)
        for _, t in sells.iterrows():
            ax1.axvline(t["timestamp"], color="#c53030", alpha=0.2, linewidth=1)

    ax1.set_title("Évolution réelle de la valeur du portefeuille (paper trading live)", fontsize=13, fontweight="bold")
    ax1.set_ylabel("USD")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.3)

    ax2 = axes[1]
    ax2.plot(equity_df["timestamp"], equity_df["btc_price"], color="#4a5568", linewidth=1)
    ax2.set_title("Prix BTC/USD sur la même période", fontsize=13, fontweight="bold")
    ax2.set_ylabel("USD")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_PATH, dpi=130)
    plt.close(fig)

    start_equity = equity_df["equity"].iloc[0]
    current_equity = equity_df["equity"].iloc[-1]
    change_pct = (current_equity - start_equity) / start_equity * 100
    n_trades = len(trades_df) if not trades_df.empty else 0

    print(f"\n=== Performance réelle depuis le début ===")
    print(f"Nombre de points enregistrés : {len(equity_df)}")
    print(f"Période : {equity_df['timestamp'].min()} → {equity_df['timestamp'].max()}")
    print(f"Valeur de départ : {start_equity:,.2f}$")
    print(f"Valeur actuelle : {current_equity:,.2f}$")
    print(f"Évolution : {change_pct:+.2f}%")
    print(f"Nombre de trades exécutés : {n_trades}")
    print(f"\nDashboard généré : {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
