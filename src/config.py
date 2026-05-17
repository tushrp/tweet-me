import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# GitHub
GITHUB_TOKEN: str = os.environ["GITHUB_TOKEN"]
GITHUB_USERNAME: str = os.environ["GITHUB_USERNAME"]
BOT_OWNER_NAME: str = os.environ.get("BOT_OWNER_NAME", GITHUB_USERNAME)
BOT_OWNER_HANDLE: str = os.environ.get("BOT_OWNER_HANDLE", f"@{GITHUB_USERNAME}")

# OpenAI
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL_DRAFT: str = os.environ.get("OPENAI_MODEL_DRAFT", "gpt-4o")

# Telegram
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: int = int(os.environ["TELEGRAM_CHAT_ID"]) if os.environ.get("TELEGRAM_CHAT_ID") else 0

# Twitter
TWITTER_API_KEY: str = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET: str = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN: str = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET: str = os.environ.get("TWITTER_ACCESS_SECRET", "")
TWITTER_BEARER_TOKEN: str = os.environ.get("TWITTER_BEARER_TOKEN", "")
TWITTER_CLIENT_ID: str = os.environ.get("TWITTER_CLIENT_ID", "")
TWITTER_CLIENT_SECRET: str = os.environ.get("TWITTER_CLIENT_SECRET", "")
TWITTER_OAUTH2_ACCESS_TOKEN: str = os.environ.get("TWITTER_OAUTH2_ACCESS_TOKEN", "")
TWITTER_OAUTH2_REFRESH_TOKEN: str = os.environ.get("TWITTER_OAUTH2_REFRESH_TOKEN", "")

# Misc
TIMEZONE = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Kolkata"))
REPO_BLACKLIST: set[str] = set(os.environ.get("REPO_BLACKLIST", "").split(",")) - {""}
TWEET_SIGNATURE: str = os.environ.get("TWEET_SIGNATURE", "")

# Paths
ROOT_DIR = Path(__file__).parent.parent
_persona = Path(__file__).parent / "persona.md"
PERSONA_PATH = _persona if _persona.exists() else Path(__file__).parent / "persona.md.example"
LOGS_DIR = ROOT_DIR / "logs"
try:
    LOGS_DIR.mkdir(exist_ok=True)
    LOGS_WRITABLE = True
except OSError:
    LOGS_WRITABLE = False
