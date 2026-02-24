"""xiaoclaw - Lightweight AI Agent compatible with OpenClaw"""

from .core import XiaClaw, XiaClawConfig, VERSION
from .utils import SecurityManager, RateLimiter, TokenStats, HookManager
from .providers import ProviderManager, ProviderConfig
from .session import Session, SessionManager
from .memory import MemoryManager
from .skills import SkillRegistry, Skill
from .web import web_search, web_fetch
from .plugins import PluginManager
from .battle import BattleEngine, BattleToolWrapper, PRESET_ROLES

__version__ = VERSION
__all__ = [
    "XiaClaw", "XiaClawConfig", "VERSION",
    "SecurityManager", "RateLimiter", "TokenStats", "HookManager",
    "ProviderManager", "ProviderConfig",
    "Session", "SessionManager",
    "MemoryManager",
    "SkillRegistry", "Skill",
    "web_search", "web_fetch",
    "PluginManager",
    "BattleEngine", "BattleToolWrapper", "PRESET_ROLES",
]
