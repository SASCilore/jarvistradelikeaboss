"""
Envoie des notifications Telegram sur ton téléphone.
"""
import os
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Non configuré (variables manquantes) — notification ignorée.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
        if resp.status_code != 200:
            print(f"[Telegram] Échec de l'envoi : {resp.text}")
    except Exception as e:
        print(f"[Telegram] Erreur d'envoi : {e}")


def notify_trade(action: str, price: float, size_usd: float, cash: float, btc_holdings: float):
    emoji = "🟢" if action == "BUY" else "🔴"
    equity = cash + btc_holdings * price
    text = (
        f"{emoji} {action} — BTC/USD @ {price:,.2f}$\n"
        f"Montant : {size_usd:,.2f}$\n"
        f"Solde cash : {cash:,.2f}$ | BTC détenu : {btc_holdings:.6f}\n"
        f"Équité totale : {equity:,.2f}$"
    )
    send_telegram_message(text)


def notify_daily_summary(report: dict):
    lines = ["📊 Résumé quotidien du bot (paper trading)"]
    for k, v in report.items():
        lines.append(f"{k} : {v}")
    send_telegram_message("\n".join(lines))


def notify_error(message: str):
    send_telegram_message(f"⚠️ Erreur du bot : {message}")
