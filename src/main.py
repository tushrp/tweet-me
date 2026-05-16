import logging
import traceback

import config  # noqa: F401 — triggers env load and dir creation
import github_fetch
import llm
import storage
import telegram_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(config.LOGS_DIR / "nightly.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def run_nightly() -> None:
    logger.info("nightly run started")

    try:
        commits = github_fetch.fetch_recent_commits(hours=24)
        stale_repos = github_fetch.fetch_stale_repos(stale_after_days=14)
        logger.info(f"fetched {len(commits)} commits, {len(stale_repos)} stale repos")

        recent = storage.get_recent_posted_tweets(days=7)
        decision = llm.decide(commits, recent, stale_repos)
        storage.log_decision(decision.should_post, decision.mood, decision.reasoning, len(commits))
        logger.info(f"decision: should_post={decision.should_post} mood={decision.mood} reason={decision.reasoning}")

        if not decision.should_post:
            logger.info("bot decided to stay silent today")
            return

        drafts = llm.draft(commits, recent, decision.mood, stale_repos)
        if not drafts:
            logger.info("no valid drafts generated")
            return

        logger.info(f"generated {len(drafts)} draft(s)")
        draft_dicts = [{"tweet": d.tweet, "confidence": d.confidence, "angle": d.angle} for d in drafts]
        draft_ids = storage.save_pending_drafts(draft_dicts, commits)

        telegram_bot.send_drafts(draft_dicts, draft_ids)
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
