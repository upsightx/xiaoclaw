#!/usr/bin/env python3
"""xiaoclaw - Lightweight AI Agent compatible with OpenClaw ecosystem"""
import os
import re
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

from .providers import ProviderManager, ProviderConfig
from .session import Session, SessionManager, count_messages_tokens
from .memory import MemoryManager
from .skills import SkillRegistry, register_builtin_skills
from .tools import ToolRegistry, TOOL_DEFS

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s %(message)s')
logger = logging.getLogger("xiaoclaw")

VERSION = "0.3.0"

# ─── Config ───────────────────────────────────────────

@dataclass
class XiaClawConfig:
    debug: bool = False
    security_level: str = "strict"
    workspace: str = "."
    max_context_tokens: int = 8000
    compaction_threshold: int = 6000
    default_model: str = "claude-opus-4-6"
    api_key: str = ""
    base_url: str = "https://ai.ltcraft.cn:12000/v1"

    @classmethod
    def from_env(cls) -> "XiaClawConfig":
        return cls(
            debug=os.getenv("XIAOCLAW_DEBUG", "false").lower() == "true",
            security_level=os.getenv("XIAOCLAW_SECURITY", "strict"),
            workspace=os.getenv("XIAOCLAW_WORKSPACE", "."),
            max_context_tokens=int(os.getenv("XIAOCLAW_MAX_TOKENS", "8000")),
            compaction_threshold=int(os.getenv("XIAOCLAW_COMPACT_THRESHOLD", "6000")),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://ai.ltcraft.cn:12000/v1"),
            default_model=os.getenv("XIAOCLAW_MODEL", "claude-opus-4-6"),
        )

    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> "XiaClawConfig":
        """Load from YAML file, env vars override."""
        try:
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return cls.from_env()

        def _resolve(val):
            """Resolve ${ENV_VAR} references."""
            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                return os.getenv(val[2:-1], "")
            return val

        cfg = data.get("agent", data)
        providers = data.get("providers", {})
        default_provider = providers.get(data.get("active_provider", "default"), {})

        return cls(
            debug=cfg.get("debug", os.getenv("XIAOCLAW_DEBUG", "false").lower() == "true"),
            security_level=cfg.get("security", os.getenv("XIAOCLAW_SECURITY", "strict")),
            workspace=cfg.get("workspace", os.getenv("XIAOCLAW_WORKSPACE", ".")),
            max_context_tokens=cfg.get("max_context_tokens", int(os.getenv("XIAOCLAW_MAX_TOKENS", "8000"))),
            compaction_threshold=cfg.get("compaction_threshold", int(os.getenv("XIAOCLAW_COMPACT_THRESHOLD", "6000"))),
            api_key=_resolve(default_provider.get("api_key", os.getenv("OPENAI_API_KEY", ""))),
            base_url=default_provider.get("base_url", os.getenv("OPENAI_BASE_URL", "https://ai.ltcraft.cn:12000/v1")),
            default_model=default_provider.get("default_model", os.getenv("XIAOCLAW_MODEL", "claude-opus-4-6")),
        )

# ─── Security ─────────────────────────────────────────

DANGEROUS = ["rm -rf", "dd if=", "mkfs", "> /dev/", "format c:", "del /f"]
class SecurityManager:
    def __init__(self, level: str = "strict", workspace: Path = Path(".")):
        self.level = level
        self._audit_log = workspace / ".xiaoclaw" / "audit.log"

    def is_dangerous(self, action: str) -> bool:
        if self.level == "relaxed":
            return False
        dangerous = any(p in action.lower() for p in DANGEROUS)
        if dangerous:
            self._audit("BLOCKED", action)
        return dangerous

    def _audit(self, event: str, detail: str):
        """Append to audit log."""
        try:
            self._audit_log.parent.mkdir(parents=True, exist_ok=True)
            import time as _t
            ts = _t.strftime("%Y-%m-%d %H:%M:%S")
            with open(self._audit_log, "a") as f:
                f.write(f"[{ts}] {event}: {detail[:200]}\n")
        except Exception:
            pass

    def log_tool_call(self, tool: str, args: dict):
        """Log tool invocations for audit."""
        self._audit("TOOL", f"{tool}({list(args.keys())})")

# ─── Rate Limiter ─────────────────────────────────────
import time as _time
class RateLimiter:
    """Simple token-bucket rate limiter."""
    def __init__(self, max_calls: int = 30, window_sec: int = 60):
        self.max_calls = max_calls
        self.window = window_sec
        self._calls: Dict[str, List[float]] = {}  # key → timestamps

    def check(self, key: str = "default") -> bool:
        """Return True if allowed, False if rate-limited."""
        now = _time.time()
        calls = self._calls.setdefault(key, [])
        # Prune old entries
        self._calls[key] = [t for t in calls if now - t < self.window]
        if len(self._calls[key]) >= self.max_calls:
            return False
        self._calls[key].append(now)
        return True

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
        """Record usage from an API response."""
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
    """before_tool_call / after_tool_call / message_received hooks."""

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
# ─── xiaoclaw Core ────────────────────────────────────
class XiaClaw:
    def __init__(self, config: Optional[XiaClawConfig] = None):
        self.config = config or XiaClawConfig.from_env()
        self.workspace = Path(self.config.workspace)
        self.security = SecurityManager(self.config.security_level, self.workspace)
        self.rate_limiter = RateLimiter()
        self.stats = TokenStats()
        self.memory = MemoryManager(self.workspace)
        self.tools = ToolRegistry(self.security, memory=self.memory)
        self.hooks = HookManager()
        self.session_mgr = SessionManager(self.workspace / ".xiaoclaw" / "sessions")
        self.session = self.session_mgr.new_session()

        # Providers
        self.providers = ProviderManager()
        if self.config.api_key:
            self.providers.add(ProviderConfig(
                name="default", api_key=self.config.api_key,
                base_url=self.config.base_url,
                models=[self.config.default_model],
                default_model=self.config.default_model,
            ))

        # Skills
        self.skills = SkillRegistry()
        register_builtin_skills(self.skills)
        skills_dir = Path(__file__).parent.parent / "skills"
        if skills_dir.exists():
            self.skills.load_from_dir(skills_dir)

        # Bootstrap system prompt from workspace files
        self._bootstrap_context = self._load_bootstrap()
        logger.info(f"xiaoclaw v{VERSION} ready | model={self.config.default_model}")

    def _load_bootstrap(self) -> str:
        """Read AGENTS.md, SOUL.md, USER.md, IDENTITY.md for system prompt."""
        parts = []
        files = self.memory.read_bootstrap_files()
        for name, content in files.items():
            parts.append(f"--- {name} ---\n{content[:2000]}")
        # Recent memory
        daily = self.memory.read_recent_daily(days=2)
        for date, content in daily.items():
            parts.append(f"--- memory/{date}.md ---\n{content[:1000]}")
        return "\n\n".join(parts)

    def _system_prompt(self) -> str:
        # Check for custom template
        template_file = self.workspace / ".xiaoclaw" / "prompt.txt"
        if template_file.exists():
            try:
                tmpl = template_file.read_text(encoding="utf-8")
                return tmpl.replace("{{version}}", VERSION).replace(
                    "{{tools}}", ", ".join(self.tools.list_names())
                ).replace("{{bootstrap}}", self._bootstrap_context[:3000])
            except Exception:
                pass

        tool_list = ", ".join(self.tools.list_names())
        skill_info = ""
        active = self.skills.get_active_skills()
        if active:
            skill_info = "\nActive skills: " + ", ".join(s.name for s in active)
        bootstrap = ""
        if self._bootstrap_context:
            bootstrap = f"\n\n## Workspace Context\n{self._bootstrap_context[:3000]}"
        return (
            f"你是 xiaoclaw v{VERSION}，一个兼容OpenClaw生态的轻量级AI Agent。\n"
            f"工具: {tool_list}{skill_info}\n"
            f"保持简洁、专业、高效。{bootstrap}"
        )

    async def _compact(self):
        """Compress old messages when exceeding token threshold. Uses LLM summary if available."""
        tokens = count_messages_tokens(self.session.messages)
        if tokens < self.config.compaction_threshold:
            return

        logger.info(f"Compacting: {tokens} tokens > {self.config.compaction_threshold}")
        self.memory.flush_important(self.session.messages)

        n = len(self.session.messages)
        if n <= 4:
            return

        old_msgs = self.session.messages[:n - 4]
        recent = self.session.messages[n - 4:]

        # Try LLM-based summary
        summary = await self._llm_summarize(old_msgs)
        if not summary:
            # Fallback: simple truncation
            summary_text = []
            for m in old_msgs:
                c = m.get("content", "")
                if isinstance(c, str) and c.strip():
                    summary_text.append(f"{m['role']}: {c[:100]}")
            summary = "[Compacted]\n" + "\n".join(summary_text[-10:])

        self.session.messages = [
            {"role": "system", "content": summary, "ts": 0}
        ] + recent
        self.session.save()
        logger.info(f"Compacted to {len(self.session.messages)} messages")

    async def _llm_summarize(self, messages: list) -> str:
        """Use LLM to summarize old messages for compaction."""
        if not (self.providers.active and self.providers.active.ready):
            return ""
        try:
            text = "\n".join(
                f"{m['role']}: {m.get('content', '')[:200]}"
                for m in messages if isinstance(m.get('content'), str) and m['content'].strip()
            )[:3000]
            resp = await self.providers.active.client.chat.completions.create(
                model=self.providers.active.current_model,
                messages=[
                    {"role": "system", "content": "Summarize this conversation concisely. Keep key facts, decisions, and context. Output in the same language as the conversation."},
                    {"role": "user", "content": text},
                ],
                max_tokens=500,
            )
            summary = resp.choices[0].message.content or ""
            if summary:
                return f"[Conversation Summary]\n{summary}"
        except Exception as e:
            logger.warning(f"LLM summarize failed: {e}")
        return ""

    async def _llm_call_with_retry(self, client, model, messages, **kwargs):
        """LLM call with exponential backoff retry. Returns response or raises."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await client.chat.completions.create(
                    model=model, messages=messages, **kwargs
                )
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait = (2 ** attempt) + 0.5
                logger.warning(f"LLM retry {attempt+1}/{max_retries} after {wait}s: {e}")
                await asyncio.sleep(wait)

    async def _agent_loop(self, sys_prompt: str, stream: bool = False):
        """Core agent loop: LLM → tool calls → repeat. Yields chunks if stream=True."""
        max_rounds = 10
        client = self.providers.active.client
        model = self.providers.active.current_model

        for _ in range(max_rounds):
            ctx = self.session.get_context_window(self.config.max_context_tokens)
            all_msgs = [{"role": "system", "content": sys_prompt}] + ctx

            try:
                resp = await self._llm_call_with_retry(
                    client, model, all_msgs,
                    tools=self.tools.openai_functions(), max_tokens=2000,
                )
            except Exception as e:
                logger.error(f"LLM error after retries: {e}")
                yield f"[LLM Error: {e}]"; return

            self.stats.record(getattr(resp, 'usage', None))
            choice = resp.choices[0]

            if choice.message.tool_calls:
                tc_msg = {"role": "assistant", "content": choice.message.content or "",
                          "tool_calls": [{"id": tc.id, "type": "function",
                                          "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                         for tc in choice.message.tool_calls]}
                self.session.add_message(**tc_msg)

                # Execute tool calls (parallel if multiple)
                async def _run_tool(tc):
                    name = tc.function.name
                    try: args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError: args = {}
                    await self.hooks.fire("before_tool_call", tool=name, args=args)
                    self.security.log_tool_call(name, args)
                    result = self.tools.call(name, args)
                    self.stats.record_tool()
                    await self.hooks.fire("after_tool_call", tool=name, args=args, result=result)
                    logger.info(f"Tool: {name}({list(args.keys())}) → {len(result)} chars")
                    return tc, name, args, result

                tool_calls = choice.message.tool_calls
                if len(tool_calls) > 1:
                    results = await asyncio.gather(*[_run_tool(tc) for tc in tool_calls])
                else:
                    results = [await _run_tool(tool_calls[0])]

                for tc, name, args, result in results:
                    self.session.add_message("tool", result, tool_call_id=tc.id, name=name)
                    if stream:
                        yield f"\n  ⚙ {name}({', '.join(f'{k}=' for k in args)})\n"
                continue

            # Final response — stream it if requested
            if stream:
                # Re-do as streaming call (no tools this round)
                ctx = self.session.get_context_window(self.config.max_context_tokens)
                all_msgs = [{"role": "system", "content": sys_prompt}] + ctx
                full = ""
                try:
                    async for chunk in await client.chat.completions.create(
                        model=model, messages=all_msgs, max_tokens=2000, stream=True,
                    ):
                        delta = chunk.choices[0].delta.content or "" if chunk.choices else ""
                        if delta:
                            full += delta
                            yield delta
                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    full = choice.message.content or ""
                    yield full
                text = re.sub(r'<think>.*?</think>\s*', '', full, flags=re.DOTALL).strip()
                if text:
                    self.session.add_message("assistant", text)
                return

            text = choice.message.content or ""
            text = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()
            if text:
                self.session.add_message("assistant", text)
            yield text; return

        yield "[Agent loop exceeded max rounds]"

    async def handle_message(self, message: str, user_id: str = "default") -> str:
        """Process a user message, return full response."""
        if not self.rate_limiter.check(user_id):
            return "⚠️ Rate limited. Please wait a moment."
        await self.hooks.fire("message_received", message=message)
        self.skills.activate_for_message(message)
        self.session.add_message("user", message)
        await self._compact()

        if not (self.providers.active and self.providers.active.ready):
            return self._fallback(message)

        parts = []
        async for chunk in self._agent_loop(self._system_prompt(), stream=False):
            parts.append(chunk)
        return "".join(parts)

    async def handle_message_stream(self, message: str, user_id: str = "default"):
        """Process a user message, yield streaming chunks."""
        if not self.rate_limiter.check(user_id):
            yield "⚠️ Rate limited. Please wait a moment."; return
        await self.hooks.fire("message_received", message=message)
        self.skills.activate_for_message(message)
        self.session.add_message("user", message)
        await self._compact()

        if not (self.providers.active and self.providers.active.ready):
            yield self._fallback(message); return

        async for chunk in self._agent_loop(self._system_prompt(), stream=True):
            yield chunk

    def _fallback(self, message: str) -> str:
        if "你好" in message or "hello" in message.lower():
            return f"你好！我是 xiaoclaw v{VERSION}。配置 OPENAI_API_KEY 后可智能对话。"
        if "工具" in message or "tools" in message.lower():
            return f"工具: {', '.join(self.tools.list_names())}"
        return f"[无LLM] 收到: {message[:100]}"

    def health_check(self) -> Dict[str, Any]:
        """Return health status for monitoring."""
        p = self.providers.active
        return {
            "status": "ok",
            "version": VERSION,
            "model": p.current_model if p else None,
            "provider_ready": bool(p and p.ready),
            "session_id": self.session.session_id,
            "message_count": len(self.session.messages),
            "stats": {
                "total_tokens": self.stats.total_tokens,
                "requests": self.stats.requests,
                "tool_calls": self.stats.tool_calls,
            },
        }
