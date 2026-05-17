import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from apscheduler.schedulers.background import BackgroundScheduler

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _nightly():
    from pipeline import run_nightly
    run_nightly()


scheduler = BackgroundScheduler(timezone=config.TIMEZONE)
scheduler.add_job(_nightly, "cron", hour=2, minute=30)
scheduler.start()
logger.info("scheduler started — nightly 02:30 (%s)", config.TIMEZONE)

from telegram_bot import run_bot
run_bot()
