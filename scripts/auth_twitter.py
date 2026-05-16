"""
One-time OAuth 2.0 setup. Run this once to authorize the app and save tokens to .env.
Requires TWITTER_CLIENT_ID and TWITTER_CLIENT_SECRET in .env (from the Developer Portal OAuth 2.0 section).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import tweepy
import config

handler = tweepy.OAuth2UserHandler(
    client_id=config.TWITTER_CLIENT_ID,
    redirect_uri="https://localhost",
    scope=["tweet.read", "tweet.write", "users.read", "offline.access"],
    client_secret=config.TWITTER_CLIENT_SECRET,
)

url = handler.get_authorization_url()
print(f"\n1. open this URL in your browser:\n\n   {url}\n")
print("2. authorize the app")
print("3. you'll be redirected to https://localhost?code=... (it'll show an error — that's fine)")
print("4. copy the FULL redirect URL from your browser and paste it below\n")

response_url = input("paste the redirect URL: ").strip()
token = handler.fetch_token(response_url)

access_token = token["access_token"]
refresh_token = token.get("refresh_token", "")

env_path = Path(__file__).parent.parent / ".env"
env_text = env_path.read_text()

def upsert_env(text, key, value):
    if f"{key}=" in text:
        lines = text.splitlines()
        lines = [f"{key}={value}" if l.startswith(f"{key}=") else l for l in lines]
        return "\n".join(lines) + "\n"
    return text + f"\n{key}={value}\n"

env_text = upsert_env(env_text, "TWITTER_OAUTH2_ACCESS_TOKEN", access_token)
env_text = upsert_env(env_text, "TWITTER_OAUTH2_REFRESH_TOKEN", refresh_token)
env_path.write_text(env_text)

print("\nTokens saved to .env. Twitter posting is ready.")
