import logging
import traceback

import config  # noqa: F401 — triggers env load
import github_fetch
import llm
import telegram_bot
import twitter

_handlers: list[logging.Handler] = [logging.StreamHandler()]
if config.LOGS_WRITABLE:
    _handlers.append(logging.FileHandler(config.LOGS_DIR / "nightly.log"))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=_handlers,
)
logger = logging.getLogger(__name__)


def _apply_signature(text: str) -> str:
    if config.TWEET_SIGNATURE:
        return f"{text}\n\n{config.TWEET_SIGNATURE}"
    return text


def run_nightly() -> None:
    logger.info("nightly run started")

    try:
        commits = github_fetch.fetch_recent_commits(hours=24)
        logger.info(f"fetched {len(commits)} commits")

        recent = twitter.get_recent_tweets(days=7)
        drafts = llm.generate_drafts(commits, recent)

        if not drafts:
            logger.info("nothing to post today")
            return

        logger.info(f"generated {len(drafts)} draft(s)")
        draft_dicts = [
            {"tweet": _apply_signature(d.tweet), "confidence": d.confidence, "angle": d.angle}
            for d in drafts
        ]

        telegram_bot.send_drafts(draft_dicts)
        logger.info("drafts sent to telegram")

    except Exception:
        err = traceback.format_exc()
        logger.error(f"nightly run failed:\n{err}")
        try:
            telegram_bot.notify_error_sync(err)
        except Exception:
            pass


if __name__ == "__main__":
    run_nightly()
