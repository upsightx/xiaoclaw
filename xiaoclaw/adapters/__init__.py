"""Adapters - 平台适配器"""

from .feishu import FeishuAdapter, get_feishu_client

__all__ = ["FeishuAdapter", "get_feishu_client"]

# Lazy imports for optional deps
def get_telegram_adapter():
    from .telegram import TelegramAdapter
    return TelegramAdapter

def get_discord_adapter():
    from .discord_adapter import DiscordAdapter
    return DiscordAdapter

def get_slack_adapter():
    from .slack_adapter import SlackAdapter
    return SlackAdapter
