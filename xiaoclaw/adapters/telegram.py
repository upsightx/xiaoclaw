"""xiaoclaw Telegram Adapter - python-telegram-bot integration"""
import os
import logging
from typing import Optional, TYPE_CHECKING

logger = logging.getLogger("xiaoclaw.Telegram")

try:
    from telegram import Update
    from telegram.ext import (
        Application, CommandHandler, MessageHandler, filters, ContextTypes,
    )
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    # For type hints when module not installed
    if TYPE_CHECKING:
        from telegram import Update
        from telegram.ext import ContextTypes


class TelegramAdapter:
    """Bridges Telegram messages to xiaoclaw.handle_message."""

    def __init__(self, token: str = "", allowed_users: Optional[list] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        # Validate and normalize allowed_users to int IDs
        if allowed_users:
            self.allowed_users = [int(u) for u in allowed_users]
        else:
            self.allowed_users = None
        self.claw = None  # set via .start(claw)
        # Per-user session storage
        self._sessions: dict = {}
        if not HAS_TELEGRAM:
            logger.error("python-telegram-bot not installed. pip install 'xiaoclaw[telegram]'")

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._check_user(update):
            return
        await update.message.reply_text(
            "🐾 xiaoclaw ready! Send me a message to chat."
        )

    async def _cmd_clear(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._check_user(update) or not self.claw:
            return
        uid = update.effective_user.id
        # Create new session for this user only
        self._sessions[uid] = self.claw.session_mgr.new_session()
        await update.message.reply_text("🔄 New session started.")

    async def _cmd_tools(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._check_user(update) or not self.claw:
            return
        tools = ", ".join(self.claw.tools.list_names())
        await update.message.reply_text(f"🔧 Tools: {tools}")

    async def _handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._check_user(update) or not self.claw:
            return
        text = update.message.text
        if not text:
            return
        # Sanitize log output to prevent log injection
        safe_text = text[:80].replace('\n', '\\n').replace('\r', '\\r')
        logger.info("TG [%s]: %s", update.effective_user.id, safe_text)
        try:
            # Use per-user session
            uid = update.effective_user.id
            if uid not in self._sessions:
                self._sessions[uid] = self.claw.session_mgr.new_session()
            # Temporarily swap session for this user
            old_session = self.claw.session
            self.claw.session = self._sessions[uid]
            try:
                reply = await self.claw.handle_message(text)
            finally:
                self.claw.session = old_session
            # Telegram has 4096 char limit per message
            for i in range(0, len(reply), 4000):
                await update.message.reply_text(reply[i:i + 4000])
        except Exception as e:
            logger.error(f"Handle error: {e}")
            await update.message.reply_text("❌ Something went wrong, please try again.")

    def _check_user(self, update: Update) -> bool:
        if self.allowed_users is None:
            return True
        uid = update.effective_user.id
        if uid not in self.allowed_users:
            logger.warning(f"Unauthorized user: {uid}")
            return False
        return True

    def start(self, claw):
        """Start the Telegram bot (blocking). Pass a XiaClaw instance."""
        if not HAS_TELEGRAM:
            raise RuntimeError("python-telegram-bot not installed")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")

        self.claw = claw
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("clear", self._cmd_clear))
        app.add_handler(CommandHandler("tools", self._cmd_tools))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        logger.info("Telegram bot starting...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


def run_telegram_bot(claw=None):
    """Convenience: create adapter and run."""
    from ..core import XiaClaw, XiaClawConfig
    if claw is None:
        claw = XiaClaw(XiaClawConfig.from_env())
    adapter = TelegramAdapter()
    adapter.start(claw)


__all__ = ["TelegramAdapter", "run_telegram_bot"]
