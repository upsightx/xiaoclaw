"""xiaoclaw - Lightweight AI Agent compatible with OpenClaw"""

from .core import XiaClaw, XiaClawConfig, VERSION, TokenStats, RateLimiter
from .providers import ProviderManager, ProviderConfig
from .session import Session, SessionManager
from .memory import MemoryManager
from .skills import SkillRegistry, Skill
from .web import web_search, web_fetch

__version__ = VERSION
__all__ = [
    "XiaClaw", "XiaClawConfig", "VERSION", "TokenStats", "RateLimiter",
    "ProviderManager", "ProviderConfig",
    "Session", "SessionManager",
    "MemoryManager",
    "SkillRegistry", "Skill",
    "web_search", "web_fetch",
]
