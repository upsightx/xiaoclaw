"""xiaoclaw Slack Adapter — Slack Bolt integration"""
import os
import logging
from typing import Optional

logger = logging.getLogger("xiaoclaw.Slack")

try:
    from slack_bolt.async_app import AsyncApp
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    HAS_SLACK = True
except ImportError:
    HAS_SLACK = False


class SlackAdapter:
    """Bridges Slack messages to xiaoclaw.handle_message."""

    def __init__(self, bot_token: str = "", app_token: str = "",
                 allowed_channels: Optional[list] = None):
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN", "")
        self.app_token = app_token or os.getenv("SLACK_APP_TOKEN", "")
        self.allowed_channels = allowed_channels
        self.claw = None

    def _check_channel(self, channel: str) -> bool:
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
            # Remove bot mention
            import re
            text = re.sub(r'<@\w+>', '', text).strip()
            if not text:
                return
            user_id = event.get("user", "unknown")
            logger.info(f"Slack [{user_id}]: {text[:80]}")
            try:
                reply = await self.claw.handle_message(text, user_id=user_id)
                await say(reply[:3000])
            except Exception as e:
                logger.error(f"Slack handle error: {e}")
                await say(f"❌ Error: {e}")

        @app.event("message")
        async def handle_dm(event, say):
            # Only handle DMs (channel type 'im')
            if event.get("channel_type") != "im":
                return
            if event.get("bot_id"):
                return  # Ignore bot messages
            text = event.get("text", "").strip()
            if not text:
                return
            user_id = event.get("user", "unknown")
            logger.info(f"Slack DM [{user_id}]: {text[:80]}")
            try:
                reply = await self.claw.handle_message(text, user_id=user_id)
                await say(reply[:3000])
            except Exception as e:
                await say(f"❌ Error: {e}")

        import asyncio
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
