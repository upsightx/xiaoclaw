"""xiaoclaw i18n — minimal internationalization support"""
import os
import logging
import re

logger = logging.getLogger("xiaoclaw.i18n")

LANG = os.getenv("XIAOCLAW_LANG", "zh")

# Warn once about unsupported languages
_warned_langs = set()

_STRINGS = {
    "zh": {
        "greeting": "你好！我是 xiaoclaw v{version}。",
        "no_llm": "配置 OPENAI_API_KEY 后可智能对话。",
        "tools_label": "工具",
        "rate_limited": "⚠️ 请求过于频繁，请稍后再试。",
        "new_session": "🔄 新会话已创建。",
        "session_restored": "✅ 已恢复会话 {sid} ({count} 条消息)",
        "session_not_found": "❌ 未找到会话: {sid}",
        "exported": "📤 已导出到 {path}",
        "blocked": "🚫 已拦截危险命令: {cmd}",
        "system_prompt": "你是 xiaoclaw v{version}，一个兼容OpenClaw生态的轻量级AI Agent。\n工具: {tools}\n保持简洁、专业、高效。",
        "analytics_title": "📊 使用统计",
        "analytics_requests": "调用次数",
        "analytics_success": "成功率",
        "analytics_tokens": "Token 使用",
        "analytics_tools": "工具调用",
    },
    "en": {
        "greeting": "Hello! I'm xiaoclaw v{version}.",
        "no_llm": "Set OPENAI_API_KEY to enable AI chat.",
        "tools_label": "Tools",
        "rate_limited": "⚠️ Rate limited. Please wait.",
        "new_session": "🔄 New session created.",
        "session_restored": "✅ Restored session {sid} ({count} messages)",
        "session_not_found": "❌ Session not found: {sid}",
        "exported": "📤 Exported to {path}",
        "blocked": "🚫 Blocked dangerous command: {cmd}",
        "system_prompt": "You are xiaoclaw v{version}, a lightweight AI Agent compatible with OpenClaw.\nTools: {tools}\nBe concise, professional, efficient.",
        "analytics_title": "📊 Usage Statistics",
        "analytics_requests": "Requests",
        "analytics_success": "Success Rate",
        "analytics_tokens": "Tokens Used",
        "analytics_tools": "Tool Calls",
    },
}


def t(key: str, lang: str = "", **kwargs) -> str:
    """Get translated string."""
    global _warned_langs
    if lang and lang not in _STRINGS and lang not in _warned_langs:
        logger.warning(f"Unsupported language '{lang}', falling back to English. Supported: {', '.join(_STRINGS.keys())}")
        _warned_langs.add(lang)
    
    # Fall back to English for unknown languages
    lang = lang or LANG
    strings = _STRINGS.get(lang, _STRINGS["en"])
    template = strings.get(key, _STRINGS["en"].get(key, key))
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        # Remove unfilled placeholders for graceful degradation
        return re.sub(r'\{[^}]+\}', '', template).strip()
