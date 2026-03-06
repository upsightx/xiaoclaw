"""xiaoclaw Discord Adapter — discord.py integration"""
import os
import logging
from typing import Optional, TYPE_CHECKING

logger = logging.getLogger("xiaoclaw.Discord")

try:
    import discord
    from discord.ext import commands
    HAS_DISCORD = True
except ImportError:
    HAS_DISCORD = False
    if TYPE_CHECKING:
        import discord
        from discord.ext import commands


class DiscordAdapter:
    """Bridges Discord messages to xiaoclaw.handle_message."""

    def __init__(self, token: str = "", allowed_channels: Optional[list] = None,
                 command_prefix: str = "!"):
        self.token = token or os.getenv("DISCORD_BOT_TOKEN", "")
        self.allowed_channels = allowed_channels  # None = allow all
        self.command_prefix = command_prefix
        self.claw = None
        # Per-user session storage
        self._sessions: dict = {}

    def _check_channel(self, channel_id: int) -> bool:
        if self.allowed_channels is None:
            return True
        return channel_id in self.allowed_channels

    def start(self, claw):
        """Start the Discord bot (blocking). Pass a XiaClaw instance."""
        if not HAS_DISCORD:
            raise RuntimeError("discord.py not installed. pip install discord.py")
        if not self.token:
            raise ValueError("DISCORD_BOT_TOKEN not set")

        self.claw = claw
        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix=self.command_prefix, intents=intents)

        @bot.event
        async def on_ready():
            logger.info(f"Discord bot ready: {bot.user}")

        @bot.event
        async def on_message(message):
            if not self.claw:
                return
            if message.author == bot.user:
                return
            if not self._check_channel(message.channel.id):
                return

            # Handle commands
            if message.content.startswith(self.command_prefix):
                await bot.process_commands(message)
                return

            # Handle mentions or DMs
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = bot.user in message.mentions
            if not is_dm and not is_mentioned:
                return

            text = message.content.replace(f"<@{bot.user.id}>", "").strip()
            if not text:
                return

            # Sanitize log output
            safe_text = text[:80].replace('\n', '\\n').replace('\r', '\\r')
            logger.info("Discord [%s]: %s", message.author, safe_text)

            try:
                # Use per-user session
                user_id = str(message.author.id)
                if user_id not in self._sessions:
                    self._sessions[user_id] = self.claw.session_mgr.new_session()

                old_session = self.claw.session
                self.claw.session = self._sessions[user_id]
                try:
                    reply = await self.claw.handle_message(text, user_id=user_id)
                finally:
                    self.claw.session = old_session

                # Discord has 2000 char limit
                for i in range(0, len(reply), 1900):
                    await message.reply(reply[i:i + 1900])
            except Exception as e:
                logger.error(f"Discord handle error: {e}")
                await message.reply("❌ Something went wrong, please try again.")

        @bot.command(name="tools")
        async def cmd_tools(ctx):
            if not self.claw or not self._check_channel(ctx.channel.id):
                return
            tools = ", ".join(self.claw.tools.list_names())
            await ctx.send(f"🔧 Tools: {tools}")

        @bot.command(name="clear")
        async def cmd_clear(ctx):
            if not self.claw or not self._check_channel(ctx.channel.id):
                return
            user_id = str(ctx.author.id)
            self._sessions[user_id] = self.claw.session_mgr.new_session()
            await ctx.send("🔄 New session started.")

        @bot.command(name="stats")
        async def cmd_stats(ctx):
            if not self.claw or not self._check_channel(ctx.channel.id):
                return
            if not hasattr(self.claw, 'stats'):
                await ctx.send("⚠️ Stats not available")
                return
            await ctx.send(self.claw.stats.summary())

        bot.run(self.token)


def run_discord_bot(claw=None):
    """Convenience: create adapter and run."""
    from ..core import XiaClaw, XiaClawConfig
    if claw is None:
        claw = XiaClaw(XiaClawConfig.from_env())
    adapter = DiscordAdapter()
    adapter.start(claw)


__all__ = ["DiscordAdapter", "run_discord_bot"]
