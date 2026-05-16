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
import storage
import twitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_awaiting_edit = False


def _guard(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == config.TELEGRAM_CHAT_ID


def _build_keyboard(draft_ids: list[int]) -> InlineKeyboardMarkup:
    post_buttons = [InlineKeyboardButton(f"✅ Post #{i+1}", callback_data=f"post:{draft_id}") for i, draft_id in enumerate(draft_ids)]
    bottom_row = [
        InlineKeyboardButton("✏️ Edit & post", callback_data="edit"),
        InlineKeyboardButton("❌ Skip all", callback_data="skip"),
    ]
    rows = [post_buttons, bottom_row]
    return InlineKeyboardMarkup(rows)


def _format_message(drafts: list[dict], draft_ids: list[int]) -> str:
    lines = ["*draft tweets for today*\n"]
    for i, (draft, _) in enumerate(zip(drafts, draft_ids)):
        confidence_pct = int(draft["confidence"] * 100)
        lines.append(f"*{i+1}.* _{draft['angle']}_ ({confidence_pct}% confidence)")
        lines.append(f"`{draft['tweet']}`")
        lines.append("")
    return "\n".join(lines).strip()


async def _send_drafts_async(drafts: list[dict], draft_ids: list[int]) -> None:
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    async with bot:
        text = _format_message(drafts, draft_ids)
        keyboard = _build_keyboard(draft_ids)
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


def send_drafts(drafts: list[dict], draft_ids: list[int]) -> None:
    asyncio.run(_send_drafts_async(drafts, draft_ids))


async def notify_error(message: str) -> None:
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    async with bot:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=f"tweet-me error:\n{message}",
        )


def notify_error_sync(message: str) -> None:
    asyncio.run(notify_error(message))


async def _post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    query = update.callback_query
    await query.answer()

    draft_id = int(query.data.split(":")[1])
    pending = storage.get_pending_drafts()
    draft = next((d for d in pending if d["id"] == draft_id), None)

    if not draft:
        await query.edit_message_text("draft not found or already actioned.")
        return

    try:
        result = twitter.post(draft["text"])
        storage.mark_posted(draft_id, result.id, result.url)
        storage.mark_skipped()
        await query.edit_message_text(f"posted. {result.url}")
    except Exception as e:
        await query.edit_message_text(f"failed to post: {e}")


async def _edit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _awaiting_edit
    if not _guard(update):
        return
    query = update.callback_query
    await query.answer()
    _awaiting_edit = True
    await query.edit_message_text("send me the tweet text (max 280 chars):")


async def _receive_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _awaiting_edit
    if not _guard(update) or not _awaiting_edit:
        return

    text = update.message.text.strip()
    if len(text) > 280:
        await update.message.reply_text(f"too long ({len(text)} chars). try again:")
        return

    _awaiting_edit = False
    pending = storage.get_pending_drafts()
    draft_id = pending[0]["id"] if pending else None

    try:
        result = twitter.post(text)
        if draft_id:
            storage.mark_edited_and_posted(draft_id, text, result.id, result.url)
        storage.mark_skipped()
        await update.message.reply_text(f"posted. {result.url}")
    except Exception as e:
        await update.message.reply_text(f"failed to post: {e}")
        _awaiting_edit = False


async def _skip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    query = update.callback_query
    await query.answer()
    storage.mark_skipped()
    await query.edit_message_text("skipped. nothing posted today.")


async def _status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    pending = storage.get_pending_drafts()
    recent = storage.get_recent_posted_tweets(days=7)
    lines = [f"pending drafts: {len(pending)}", f"tweets this week: {len(recent)}"]
    if pending:
        lines.append("\npending:")
        for d in pending:
            lines.append(f"  - {d['text'][:60]}...")
    await update.message.reply_text("\n".join(lines))


def run_bot() -> None:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CallbackQueryHandler(_post_handler, pattern="^post:"))
    app.add_handler(CallbackQueryHandler(_edit_handler, pattern="^edit$"))
    app.add_handler(CallbackQueryHandler(_skip_handler, pattern="^skip$"))
    app.add_handler(CommandHandler("status", _status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _receive_edit_text))

    logger.info("bot started, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
