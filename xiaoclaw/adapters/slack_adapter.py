"""xiaoclaw Slack Adapter — Slack Bolt integration"""
import os
import re
import logging
import asyncio
from typing import Optional, TYPE_CHECKING

logger = logging.getLogger("xiaoclaw.Slack")

try:
    from slack_bolt.async_app import AsyncApp
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    HAS_SLACK = True
except ImportError:
    HAS_SLACK = False
    if TYPE_CHECKING:
        from slack_bolt.async_app import AsyncApp
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler


class SlackAdapter:
    """Bridges Slack messages to xiaoclaw.handle_message."""

    def __init__(self, bot_token: str = "", app_token: str = "",
                 allowed_channels: Optional[list] = None):
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN", "")
        self.app_token = app_token or os.getenv("SLACK_APP_TOKEN", "")
        self.allowed_channels = allowed_channels
        self.claw = None
        # Per-user session storage
        self._sessions: dict = {}
        # Pre-compile regex for bot mention removal
        self._mention_pattern = re.compile(r'<@\w+>')

    def _check_channel(self, channel: str) -> bool:
        """Check if channel is allowed.

        Args:
            channel: Slack channel ID.

        Returns:
            True if channel is allowed or no restriction configured.
        """
        if self.allowed_channels is None:
            return True
        return channel in self.allowed_channels

    def start(self, claw):
        """Start the Slack bot via Socket Mode (blocking)."""
        if not HAS_SLACK:
            raise RuntimeError("slack-bolt not installed. pip install slack-bolt")
        if not self.bot_token or not self.app_token:
            raise ValueError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN required")

        self.claw = claw
        app = AsyncApp(token=self.bot_token)

        @app.event("app_mention")
        async def handle_mention(event, say):
            if not self._check_channel(event.get("channel", "")):
                return
            text = event.get("text", "").strip()
            # Remove bot mention using pre-compiled regex
            text = self._mention_pattern.sub('', text).strip()
            if not text:
                return
            user_id = event.get("user", "unknown")
            safe_text = text[:80].replace('\n', '\\n')
            logger.info("Slack [%s]: %s", user_id, safe_text)
            
            # Per-user session
            if user_id not in self._sessions:
                self._sessions[user_id] = self.claw.session_mgr.new_session()
            old_session = self.claw.session
            self.claw.session = self._sessions[user_id]
            try:
                reply = await self.claw.handle_message(text, user_id=user_id)
            finally:
                self.claw.session = old_session
            
            # Chunk long messages (Slack limit 3000)
            for i in range(0, len(reply), 3000):
                await say(reply[i:i + 3000])

        @app.event("message")
        async def handle_dm(event, say):
            # Only handle plain messages (ignore subtypes)
            if event.get("subtype"):
                return
            # Only handle DMs (channel type 'im')
            if event.get("channel_type") != "im":
                return
            if event.get("bot_id"):
                return  # Ignore bot messages
            text = event.get("text", "").strip()
            if not text:
                return
            user_id = event.get("user", "unknown")
            safe_text = text[:80].replace('\n', '\\n')
            logger.info("Slack DM [%s]: %s", user_id, safe_text)
            
            # Per-user session
            if user_id not in self._sessions:
                self._sessions[user_id] = self.claw.session_mgr.new_session()
            old_session = self.claw.session
            self.claw.session = self._sessions[user_id]
            try:
                reply = await self.claw.handle_message(text, user_id=user_id)
            finally:
                self.claw.session = old_session
            
            # Chunk long messages
            for i in range(0, len(reply), 3000):
                await say(reply[i:i + 3000])

        async def _run():
            handler = AsyncSocketModeHandler(app, self.app_token)
            logger.info("Slack bot starting (Socket Mode)...")
            await handler.start_async()

        asyncio.run(_run())


def run_slack_bot(claw=None):
    """Convenience: create adapter and run."""
    from ..core import XiaClaw, XiaClawConfig
    if claw is None:
        claw = XiaClaw(XiaClawConfig.from_env())
    adapter = SlackAdapter()
    adapter.start(claw)


__all__ = ["SlackAdapter", "run_slack_bot"]
