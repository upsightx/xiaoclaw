#!/usr/bin/env python3
"""XiaClaw - Lightweight AI Agent compatible with OpenClaw ecosystem"""
import os
import re
import json
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

from .providers import ProviderManager, ProviderConfig
from .session import Session, SessionManager, count_messages_tokens
from .memory import MemoryManager
from .skills import SkillRegistry, register_builtin_skills

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s %(message)s')
logger = logging.getLogger("XiaClaw")

VERSION = "0.2.0"

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

# ─── Security ─────────────────────────────────────────

DANGEROUS = ["rm -rf", "dd if=", "mkfs", "> /dev/", "format c:", "del /f"]

class SecurityManager:
    def __init__(self, level: str = "strict"):
        self.level = level

    def is_dangerous(self, action: str) -> bool:
        if self.level == "relaxed":
            return False
        return any(p in action.lower() for p in DANGEROUS)

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

# ─── Built-in Tools ──────────────────────────────────

class ToolRegistry:
    def __init__(self, security: SecurityManager):
        self.tools: Dict[str, Dict] = {}
        self.security = security
        self._register_builtins()

    def _register_builtins(self):
        self.register("read", self._read, "Read file contents")
        self.register("write", self._write, "Write content to file")
        self.register("edit", self._edit, "Edit file (find & replace)")
        self.register("exec", self._exec, "Execute shell command")
        self.register("web_search", self._web_search, "Search the web")
        self.register("web_fetch", self._web_fetch, "Fetch webpage content")
        self.register("memory_search", self._noop, "Search memory (handled by core)")
        self.register("memory_get", self._noop, "Get memory content (handled by core)")

    def register(self, name: str, func: Callable, desc: str = ""):
        self.tools[name] = {"func": func, "description": desc}

    def get(self, name: str): return self.tools.get(name)
    def list_names(self) -> List[str]: return list(self.tools.keys())

    def _noop(self, **kw): return ""

    def _read(self, file_path: str = "", path: str = "", **kw) -> str:
        p = Path(file_path or path).expanduser()
        if not p.exists(): return f"Error: not found: {p}"
        try: return p.read_text(encoding="utf-8")[:10000]
        except Exception as e: return f"Error: {e}"

    def _write(self, file_path: str = "", path: str = "", content: str = "", **kw) -> str:
        p = Path(file_path or path).expanduser()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Written: {p}"
        except Exception as e: return f"Error: {e}"

    def _edit(self, file_path: str = "", path: str = "", old_string: str = "",
              new_string: str = "", **kw) -> str:
        p = Path(file_path or path).expanduser()
        if not p.exists(): return f"Error: not found: {p}"
        try:
            text = p.read_text(encoding="utf-8")
            if old_string not in text: return "Error: old_string not found"
            p.write_text(text.replace(old_string, new_string, 1), encoding="utf-8")
            return f"Edited: {p}"
        except Exception as e: return f"Error: {e}"

    def _exec(self, command: str = "", **kw) -> str:
        if self.security.is_dangerous(command):
            return f"Blocked: dangerous command: {command}"
        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return ((r.stdout + r.stderr).strip() or "(no output)")[:5000]
        except subprocess.TimeoutExpired: return "Error: timeout (30s)"
        except Exception as e: return f"Error: {e}"

    def _web_search(self, query: str = "", **kw) -> str:
        return f"[web_search stub] query: {query}"

    def _web_fetch(self, url: str = "", **kw) -> str:
        return f"[web_fetch stub] url: {url}"

# ─── XiaClaw Core ────────────────────────────────────

class XiaClaw:
    def __init__(self, config: Optional[XiaClawConfig] = None):
        self.config = config or XiaClawConfig.from_env()
        self.workspace = Path(self.config.workspace)
        self.security = SecurityManager(self.config.security_level)
        self.tools = ToolRegistry(self.security)
        self.hooks = HookManager()
        self.memory = MemoryManager(self.workspace)
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
        logger.info(f"XiaClaw v{VERSION} ready | model={self.config.default_model}")

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
        tool_list = ", ".join(self.tools.list_names())
        skill_info = ""
        active = self.skills.get_active_skills()
        if active:
            skill_info = "\nActive skills: " + ", ".join(s.name for s in active)
        bootstrap = ""
        if self._bootstrap_context:
            bootstrap = f"\n\n## Workspace Context\n{self._bootstrap_context[:3000]}"
        return (
            f"你是 XiaClaw v{VERSION}，一个兼容OpenClaw生态的轻量级AI Agent。\n"
            f"工具: {tool_list}{skill_info}\n"
            f"保持简洁、专业、高效。{bootstrap}"
        )

    async def _compact(self):
        """Compress old messages when exceeding token threshold."""
        tokens = count_messages_tokens(self.session.messages)
        if tokens < self.config.compaction_threshold:
            return

        logger.info(f"Compacting: {tokens} tokens > {self.config.compaction_threshold}")
        # Flush important info before compaction
        self.memory.flush_important(self.session.messages)

        # Keep system-relevant messages and recent ones
        n = len(self.session.messages)
        if n <= 4:
            return

        old_msgs = self.session.messages[:n - 4]
        recent = self.session.messages[n - 4:]

        # Summarize old messages
        summary_text = []
        for m in old_msgs:
            c = m.get("content", "")
            if isinstance(c, str) and c.strip():
                summary_text.append(f"{m['role']}: {c[:100]}")
        summary = "[Compacted conversation summary]\n" + "\n".join(summary_text[-10:])

        self.session.messages = [
            {"role": "system", "content": summary, "ts": 0}
        ] + recent
        self.session.save()
        logger.info(f"Compacted to {len(self.session.messages)} messages")

    async def handle_message(self, message: str) -> str:
        """Process a user message and return response."""
        # Fire hook
        await self.hooks.fire("message_received", message=message)

        # Auto-activate skills
        self.skills.activate_for_message(message)

        # Add to session
        self.session.add_message("user", message)

        # Check compaction
        await self._compact()

        # Get context window
        ctx = self.session.get_context_window(self.config.max_context_tokens)

        # Call LLM
        if self.providers.active and self.providers.active.ready:
            sys_prompt = self._system_prompt()
            all_msgs = [{"role": "system", "content": sys_prompt}] + ctx
            response = await self.providers.chat(all_msgs, max_tokens=2000)
            if response:
                response = re.sub(r'<think>.*?</think>\s*', '', response, flags=re.DOTALL).strip()
                self.session.add_message("assistant", response)
                return response

        # Fallback without LLM
        return self._fallback(message)

    def _fallback(self, message: str) -> str:
        if "你好" in message or "hello" in message.lower():
            return f"你好！我是 XiaClaw v{VERSION}。配置 OPENAI_API_KEY 后可智能对话。"
        if "工具" in message or "tools" in message.lower():
            return f"工具: {', '.join(self.tools.list_names())}"
        return f"[无LLM] 收到: {message[:100]}"

# ─── CLI ─────────────────────────────────────────────

async def main():
    import sys

    print(f"\n  XiaClaw v{VERSION} - Lightweight AI Agent\n")
    config = XiaClawConfig.from_env()
    claw = XiaClaw(config)

    print(f"  Tools:     {', '.join(claw.tools.list_names())}")
    print(f"  Skills:    {', '.join(claw.skills.list_skills()) or '(none)'}")
    if claw.providers.active:
        p = claw.providers.active
        print(f"  Provider:  {p.config.name} | {p.current_model} @ {p.config.base_url}")
    else:
        print(f"  Provider:  ⚠️  not configured")
    print(f"  Session:   {claw.session.session_id}")

    if "--test" in sys.argv:
        print("\n--- Self Test ---")
        # Test providers
        from .providers import test_providers
        test_providers()
        # Test session
        from .session import test_session
        test_session()
        # Test memory
        from .memory import test_memory
        test_memory()
        # Test skills
        from .skills import test_skills
        test_skills()
        # Test core message handling
        for msg in ["你好", "工具列表", "1+1等于几？"]:
            r = await claw.handle_message(msg)
            print(f"  > {msg}\n  < {r[:200]}\n")
        print("  ✓ All tests passed!")
        return

    # Interactive mode
    print(f"\n  /help /tools /skills /model /sessions /quit\n" + "─" * 50)
    while True:
        try:
            user_input = input("\n🧑 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye! 👋"); break
        if not user_input: continue

        cmd = user_input.lower()
        if cmd in ("/quit", "/exit", "/q"):
            claw.session.save(); print("Bye! 👋"); break
        elif cmd == "/help":
            print("  /tools /skills /model /sessions /memory /clear /quit")
        elif cmd == "/tools":
            print(f"  {', '.join(claw.tools.list_names())}")
        elif cmd == "/skills":
            for n in claw.skills.list_skills():
                s = claw.skills.get_skill(n)
                print(f"  {n}: {list(s.tools.keys())}")
        elif cmd == "/model":
            for p in claw.providers.list_providers():
                mark = "→" if p["active"] else " "
                print(f"  {mark} {p['name']}: {p['model']} @ {p['base_url']}")
        elif cmd == "/sessions":
            for s in claw.session_mgr.list_sessions():
                print(f"  {s['session_id']} ({s['size']}B)")
        elif cmd == "/memory":
            mem = claw.memory.read_memory()
            print(f"  MEMORY.md: {len(mem)} chars" if mem else "  (empty)")
        elif cmd == "/clear":
            claw.session = claw.session_mgr.new_session()
            print("  New session started")
        else:
            response = await claw.handle_message(user_input)
            print(f"\n🐾 XiaClaw: {response}")


if __name__ == "__main__":
    asyncio.run(main())
