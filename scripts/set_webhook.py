"""One-time: register your Vercel URL as the Telegram webhook.

Usage:
    python scripts/set_webhook.py https://your-app.vercel.app
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import requests

import config


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python scripts/set_webhook.py https://your-app.vercel.app")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    webhook_url = f"{base_url}/api/webhook"

    resp = requests.post(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/setWebhook",
        json={"url": webhook_url, "allowed_updates": ["message", "callback_query"]},
        timeout=10,
    )
    print(f"setWebhook → {resp.status_code} {resp.text}")

    info = requests.get(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getWebhookInfo",
        timeout=10,
    )
    print(f"getWebhookInfo → {info.json()}")


if __name__ == "__main__":
    main()
