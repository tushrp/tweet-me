"""Vercel webhook handler for Telegram bot updates."""
import json
import os
from http.server import BaseHTTPRequestHandler

EDIT_PROMPT = "send me the new tweet text (reply to this message):"


def _process_update(update: dict) -> None:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    import requests
    import config
    import twitter

    telegram_api = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"

    def _is_authorized(u: dict) -> bool:
        user_id = None
        if "callback_query" in u:
            user_id = u["callback_query"]["from"]["id"]
        elif "message" in u:
            user_id = u["message"]["from"]["id"]
        return user_id == config.TELEGRAM_CHAT_ID

    def _answer_callback(callback_id: str) -> None:
        requests.post(f"{telegram_api}/answerCallbackQuery", json={"callback_query_id": callback_id}, timeout=5)

    def _edit_message(chat_id: int, message_id: int, text: str) -> None:
        requests.post(
            f"{telegram_api}/editMessageText",
            json={"chat_id": chat_id, "message_id": message_id, "text": text},
            timeout=5,
        )

    def _send_message(chat_id: int, text: str, reply_to: int | None = None, force_reply: bool = False) -> None:
        payload = {"chat_id": chat_id, "text": text}
        if reply_to:
            payload["reply_parameters"] = {"message_id": reply_to}
        if force_reply:
            payload["reply_markup"] = {"force_reply": True, "selective": True}
        requests.post(f"{telegram_api}/sendMessage", json=payload, timeout=5)

    def _apply_signature(text: str) -> str:
        if config.TWEET_SIGNATURE and not text.rstrip().endswith(config.TWEET_SIGNATURE):
            return f"{text}\n\n{config.TWEET_SIGNATURE}"
        return text

    if not _is_authorized(update):
        return

    if "callback_query" in update:
        cb = update["callback_query"]
        data = cb["data"]
        message = cb["message"]
        chat_id = message["chat"]["id"]
        msg_id = message["message_id"]
        tweet_text = message.get("text", "")

        _answer_callback(cb["id"])

        if data == "post":
            try:
                result = twitter.post(tweet_text)
                _edit_message(chat_id, msg_id, f"posted ✅\n{result.url}")
            except Exception as e:
                _edit_message(chat_id, msg_id, f"failed to post: {e}\n\noriginal:\n{tweet_text}")
        elif data == "skip":
            _edit_message(chat_id, msg_id, f"skipped.\n\noriginal:\n{tweet_text}")
        elif data == "edit":
            _send_message(chat_id, EDIT_PROMPT, reply_to=msg_id, force_reply=True)

    elif "message" in update:
        msg = update["message"]
        text = msg.get("text", "").strip()
        if not text:
            return
        reply_to = msg.get("reply_to_message")
        if not reply_to or reply_to.get("text") != EDIT_PROMPT:
            return

        chat_id = msg["chat"]["id"]
        final_text = _apply_signature(text)
        if len(final_text) > 280:
            _send_message(chat_id, f"too long ({len(final_text)} chars with signature). try again:")
            return

        try:
            result = twitter.post(final_text)
            _send_message(chat_id, f"posted ✅\n{result.url}")
        except Exception as e:
            _send_message(chat_id, f"failed to post: {e}")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
        if webhook_secret:
            sent = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if sent != webhook_secret:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"unauthorized")
                return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            update = json.loads(body)
            _process_update(update)
        except Exception as e:
            print(f"webhook error: {e}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"tweet-me webhook is alive")
