import asyncio
import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import twitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _guard(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == config.TELEGRAM_CHAT_ID


def _draft_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Post", callback_data="post"),
            InlineKeyboardButton("✏️ Edit", callback_data="edit"),
            InlineKeyboardButton("⏭️ Skip", callback_data="skip"),
        ]
    ])


async def _send_drafts_async(drafts: list[dict]) -> None:
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    async with bot:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=f"*{len(drafts)} draft(s) for today*",
            parse_mode="Markdown",
        )
        for i, draft in enumerate(drafts):
            confidence_pct = int(draft["confidence"] * 100)
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=f"_#{i+1} · {draft['angle']} · {confidence_pct}%_",
                parse_mode="Markdown",
            )
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=draft["tweet"],
                reply_markup=_draft_keyboard(),
            )


def send_drafts(drafts: list[dict]) -> None:
    asyncio.run(_send_drafts_async(drafts))


async def notify_error(message: str) -> None:
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    async with bot:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=f"tweet-me error:\n{message}",
        )


def notify_error_sync(message: str) -> None:
    asyncio.run(notify_error(message))


def _apply_signature(text: str) -> str:
    if config.TWEET_SIGNATURE and not text.rstrip().endswith(config.TWEET_SIGNATURE):
        return f"{text}\n\n{config.TWEET_SIGNATURE}"
    return text


async def _post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    query = update.callback_query
    await query.answer()

    tweet_text = query.message.text
    try:
        result = twitter.post(tweet_text)
        await query.edit_message_text(f"posted ✅\n{result.url}")
    except Exception as e:
        await query.edit_message_text(f"failed to post: {e}\n\noriginal draft:\n{tweet_text}")


async def _edit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    query = update.callback_query
    await query.answer()
    # Remember which draft we're editing
    context.user_data["editing_message_id"] = query.message.message_id
    context.user_data["editing_original"] = query.message.text
    await query.message.reply_text("send me the new tweet text:")


async def _receive_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    if "editing_message_id" not in context.user_data:
        return

    text = _apply_signature(update.message.text.strip())
    if len(text) > 280:
        await update.message.reply_text(f"too long ({len(text)} chars with signature). try again:")
        return

    context.user_data.pop("editing_message_id", None)
    context.user_data.pop("editing_original", None)

    try:
        result = twitter.post(text)
        await update.message.reply_text(f"posted ✅\n{result.url}")
    except Exception as e:
        await update.message.reply_text(f"failed to post: {e}")


async def _skip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"skipped.\n\noriginal:\n{query.message.text}")


async def _status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    recent = twitter.get_recent_tweets(days=7)
    await update.message.reply_text(f"tweets in last 7 days: {len(recent)}")


def run_bot() -> None:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CallbackQueryHandler(_post_handler, pattern="^post$"))
    app.add_handler(CallbackQueryHandler(_edit_handler, pattern="^edit$"))
    app.add_handler(CallbackQueryHandler(_skip_handler, pattern="^skip$"))
    app.add_handler(CommandHandler("status", _status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _receive_edit_text))

    logger.info("bot started, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
