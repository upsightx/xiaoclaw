"""Adapters - 平台适配器"""

from .feishu import FeishuAdapter, get_feishu_client

__all__ = ["FeishuAdapter", "get_feishu_client"]

# Lazy imports for optional deps
def get_telegram_adapter():
    from .telegram import TelegramAdapter
    return TelegramAdapter
