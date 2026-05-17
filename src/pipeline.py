import logging
import traceback

import config  # noqa: F401 — triggers env load
import github_fetch
import llm
import telegram_bot
import twitter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(config.LOGS_DIR / "nightly.log"),
        logging.StreamHandler(),
    ],
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
        stale_repos = github_fetch.fetch_stale_repos(stale_after_days=14)
        logger.info(f"fetched {len(commits)} commits, {len(stale_repos)} stale repos")

        recent = twitter.get_recent_tweets(days=7)
        decision = llm.decide(commits, recent, stale_repos)
        logger.info(f"decision: should_post={decision.should_post} mood={decision.mood} reason={decision.reasoning}")

        if not decision.should_post:
            logger.info("bot decided to stay silent today")
            return

        drafts = llm.draft(commits, recent, decision.mood, stale_repos)
        if not drafts:
            logger.info("no valid drafts generated")
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
