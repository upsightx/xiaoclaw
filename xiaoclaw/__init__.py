"""XiaClaw - Lightweight AI Agent compatible with OpenClaw"""

from .core import XiaClaw, XiaClawConfig, VERSION
from .providers import ProviderManager, ProviderConfig
from .session import Session, SessionManager
from .memory import MemoryManager
from .skills import SkillRegistry, Skill

__version__ = VERSION
__all__ = [
    "XiaClaw", "XiaClawConfig", "VERSION",
    "ProviderManager", "ProviderConfig",
    "Session", "SessionManager",
    "MemoryManager",
    "SkillRegistry", "Skill",
]
