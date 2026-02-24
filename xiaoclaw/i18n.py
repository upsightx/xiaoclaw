"""xiaoclaw i18n — minimal internationalization support"""
import os

LANG = os.getenv("XIAOCLAW_LANG", "zh")

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
    },
}


def t(key: str, lang: str = "", **kwargs) -> str:
    """Get translated string."""
    lang = lang or LANG
    strings = _STRINGS.get(lang, _STRINGS["zh"])
    template = strings.get(key, _STRINGS["zh"].get(key, key))
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
