from dataclasses import dataclass
from pathlib import Path

import requests

import config


@dataclass
class PostResult:
    id: str
    url: str


def _get_access_token() -> str:
    token = config.TWITTER_OAUTH2_ACCESS_TOKEN
    if not token:
        raise RuntimeError("no Twitter OAuth2 access token. run scripts/auth_twitter.py first.")
    return token


def _refresh_and_save() -> str:
    resp = requests.post(
        "https://api.twitter.com/2/oauth2/token",
        auth=(config.TWITTER_CLIENT_ID, config.TWITTER_CLIENT_SECRET),
        data={
            "grant_type": "refresh_token",
            "refresh_token": config.TWITTER_OAUTH2_REFRESH_TOKEN,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    new_access = data["access_token"]
    new_refresh = data.get("refresh_token", config.TWITTER_OAUTH2_REFRESH_TOKEN)

    env_path = Path(__file__).parent.parent / ".env"
    lines = env_path.read_text().splitlines()
    lines = [
        f"TWITTER_OAUTH2_ACCESS_TOKEN={new_access}" if l.startswith("TWITTER_OAUTH2_ACCESS_TOKEN=")
        else f"TWITTER_OAUTH2_REFRESH_TOKEN={new_refresh}" if l.startswith("TWITTER_OAUTH2_REFRESH_TOKEN=")
        else l
        for l in lines
    ]
    env_path.write_text("\n".join(lines) + "\n")
    return new_access


def _post_request(text: str, access_token: str) -> requests.Response:
    return requests.post(
        "https://api.twitter.com/2/tweets",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"text": text},
    )


def post(text: str) -> PostResult:
    token = _get_access_token()
    resp = _post_request(text, token)

    if resp.status_code == 401 and config.TWITTER_OAUTH2_REFRESH_TOKEN:
        token = _refresh_and_save()
        resp = _post_request(text, token)

    if not resp.ok:
        raise RuntimeError(f"twitter post failed: {resp.status_code} {resp.text}")

    tweet_id = str(resp.json()["data"]["id"])
    url = f"https://x.com/{config.GITHUB_USERNAME}/status/{tweet_id}"
    return PostResult(id=tweet_id, url=url)


def get_recent_tweets(days: int = 7) -> list[dict]:
    """Fetch your own recent tweets. Returns [] on any failure (e.g. free tier read limits)."""
    from datetime import datetime, timedelta, timezone

    try:
        user_resp = requests.get(
            f"https://api.twitter.com/2/users/by/username/{config.GITHUB_USERNAME}",
            headers={"Authorization": f"Bearer {config.TWITTER_BEARER_TOKEN}"},
            timeout=10,
        )
        if not user_resp.ok:
            return []
        user_id = user_resp.json()["data"]["id"]

        start_time = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        tweets_resp = requests.get(
            f"https://api.twitter.com/2/users/{user_id}/tweets",
            headers={"Authorization": f"Bearer {config.TWITTER_BEARER_TOKEN}"},
            params={"start_time": start_time, "max_results": 50, "tweet.fields": "created_at"},
            timeout=10,
        )
        if not tweets_resp.ok:
            return []
        data = tweets_resp.json().get("data", [])
        return [{"text": t["text"], "posted_at": t.get("created_at")} for t in data]
    except Exception:
        return []
