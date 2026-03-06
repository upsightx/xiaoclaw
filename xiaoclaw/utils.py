"""xiaoclaw Utilities — SecurityManager, RateLimiter, TokenStats, HookManager"""
import asyncio
import logging
import time as _time
from pathlib import Path
from typing import Dict, Any, List, Callable

logger = logging.getLogger("xiaoclaw")

# ─── Security ─────────────────────────────────────────

DANGEROUS = [
    "rm -rf", "rm -r -f", "rm -fr", "dd if=", "mkfs", "> /dev/",
    "format c:", "del /f", "find / -delete", "chmod -R 777",
    ":(){ :|:& };:", "wget", "curl.*|.*sh", ">/dev/sda",
    "shred -u", "mv /dev/null", "ln -s /dev/null",
]


class SecurityManager:
    def __init__(self, level: str = "strict", workspace: Path = Path(".")):
        self.level = level
        self._audit_log = workspace / ".xiaoclaw" / "audit.log"
        # Tool permission control: whitelist/blacklist per user
        self._tool_whitelist: Dict[str, set] = {}  # user_id → allowed tools
        self._tool_blacklist: Dict[str, set] = {}  # user_id → blocked tools

    def is_dangerous(self, action: str) -> bool:
        if self.level == "relaxed":
            return False
        dangerous = any(p in action.lower() for p in DANGEROUS)
        if dangerous:
            self._audit("BLOCKED", action)
        return dangerous

    def set_tool_whitelist(self, user_id: str, tools: List[str]):
        """Set allowed tools for a user (empty = allow all)."""
        self._tool_whitelist[user_id] = set(tools)

    def set_tool_blacklist(self, user_id: str, tools: List[str]):
        """Set blocked tools for a user."""
        self._tool_blacklist[user_id] = set(tools)

    def is_tool_allowed(self, tool: str, user_id: str = "default") -> bool:
        """Check if a tool is allowed for a user."""
        if user_id in self._tool_blacklist and tool in self._tool_blacklist[user_id]:
            self._audit("TOOL_BLOCKED", f"{user_id}: {tool}")
            return False
        if user_id in self._tool_whitelist:
            wl = self._tool_whitelist[user_id]
            if wl and tool not in wl:
                self._audit("TOOL_BLOCKED", f"{user_id}: {tool} (not in whitelist)")
                return False
        return True

    def _audit(self, event: str, detail: str):
        """Append to audit log."""
        try:
            self._audit_log.parent.mkdir(parents=True, exist_ok=True)
            ts = _time.strftime("%Y-%m-%d %H:%M:%S")
            with open(self._audit_log, "a") as f:
                f.write(f"[{ts}] {event}: {detail[:200]}\n")
        except Exception:
            pass

    def log_tool_call(self, tool: str, args: dict):
        """Log tool invocations for audit."""
        self._audit("TOOL", f"{tool}({list(args.keys())})")


# ─── Rate Limiter ─────────────────────────────────────

class RateLimiter:
    """Simple token-bucket rate limiter."""
    def __init__(self, max_calls: int = 30, window_sec: int = 60):
        self.max_calls = max_calls
        self.window = window_sec
        self._calls: Dict[str, List[float]] = {}

    def check(self, key: str = "default") -> bool:
        now = _time.time()
        calls = self._calls.setdefault(key, [])
        self._calls[key] = [t for t in calls if now - t < self.window]
        if len(self._calls[key]) >= self.max_calls:
            return False
        self._calls[key].append(now)
        # Cleanup: remove keys with empty call lists to prevent memory leak
        self._calls = {k: v for k, v in self._calls.items() if v}
        return True

    def cleanup(self):
        """Remove expired keys to prevent memory leak."""
        now = _time.time()
        self._calls = {
            k: [t for t in v if now - t < self.window]
            for k, v in self._calls.items()
        }
        # Remove keys with empty lists
        self._calls = {k: v for k, v in self._calls.items() if v}

    def remaining(self, key: str = "default") -> int:
        now = _time.time()
        calls = [t for t in self._calls.get(key, []) if now - t < self.window]
        return max(0, self.max_calls - len(calls))


# ─── Token Stats ──────────────────────────────────────

class TokenStats:
    """Track token usage across sessions."""
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.requests = 0
        self.tool_calls = 0

    def record(self, usage):
        if usage:
            self.prompt_tokens += getattr(usage, 'prompt_tokens', 0) or 0
            self.completion_tokens += getattr(usage, 'completion_tokens', 0) or 0
            self.total_tokens += getattr(usage, 'total_tokens', 0) or 0
        self.requests += 1

    def record_tool(self):
        self.tool_calls += 1

    def summary(self) -> str:
        return (f"📊 Tokens: {self.total_tokens} (prompt={self.prompt_tokens}, "
                f"completion={self.completion_tokens}) | "
                f"Requests: {self.requests} | Tool calls: {self.tool_calls}")

    def reset(self):
        self.prompt_tokens = self.completion_tokens = self.total_tokens = 0
        self.requests = self.tool_calls = 0


# ─── Hook System ──────────────────────────────────────

class HookManager:
    """before_tool_call / after_tool_call / message_received hooks.
    
    Note: fire() returns the result of the first hook that returns a non-None
    value, silently skipping remaining hooks (first-non-None-wins semantics).
    """

    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = {}

    def register(self, event: str, fn: Callable):
        self._hooks.setdefault(event, []).append(fn)

    async def fire(self, event: str, **kwargs) -> Any:
        for fn in self._hooks.get(event, []):
            try:
                r = fn(**kwargs) if not asyncio.iscoroutinefunction(fn) else await fn(**kwargs)
                if r is not None:
                    return r
            except Exception as e:
                logger.error(f"Hook '{event}' error: {e}")
        return None
