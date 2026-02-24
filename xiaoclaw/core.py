#!/usr/bin/env python3
"""xiaoclaw - Lightweight AI Agent compatible with OpenClaw ecosystem"""
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
from .web import web_search as _web_search, web_fetch as _web_fetch

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s %(message)s')
logger = logging.getLogger("xiaoclaw")

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
TOOL_DEFS = [
    {"name": "read", "desc": "Read a file", "params": {
        "type": "object", "properties": {"file_path": {"type": "string", "description": "Path to file"}},
        "required": ["file_path"]}},
    {"name": "write", "desc": "Write content to a file", "params": {
        "type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["file_path", "content"]}},
    {"name": "edit", "desc": "Edit a file by replacing text", "params": {
        "type": "object", "properties": {"file_path": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}},
        "required": ["file_path", "old_string", "new_string"]}},
    {"name": "exec", "desc": "Run a shell command", "params": {
        "type": "object", "properties": {"command": {"type": "string", "description": "Shell command"}},
        "required": ["command"]}},
    {"name": "web_search", "desc": "Search the web", "params": {
        "type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "web_fetch", "desc": "Fetch URL content", "params": {
        "type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "memory_search", "desc": "Search memory files", "params": {
        "type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "memory_get", "desc": "Read memory file lines", "params": {
        "type": "object", "properties": {"file_path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}},
        "required": ["file_path"]}},
]

class ToolRegistry:
    def __init__(self, security: SecurityManager, memory: Optional[Any] = None):
        self.tools: Dict[str, Dict] = {}
        self.security = security
        self.memory = memory
        for n, f, d in [
            ("read", self._read, "Read file"), ("write", self._write, "Write file"),
            ("edit", self._edit, "Edit file"), ("exec", self._exec, "Run command"),
            ("web_search", lambda **kw: _web_search(**kw), "Search web"),
            ("web_fetch", lambda **kw: _web_fetch(**kw), "Fetch URL"),
            ("memory_search", self._memory_search, "Search memory"),
            ("memory_get", self._memory_get, "Get memory"),
        ]:
            self.tools[n] = {"func": f, "description": d}

    def get(self, name: str): return self.tools.get(name)
    def list_names(self) -> List[str]: return list(self.tools.keys())

    def call(self, name: str, args: Dict) -> str:
        """Execute a tool by name with args dict."""
        tool = self.tools.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'"
        try:
            return str(tool["func"](**args))
        except Exception as e:
            return f"Error calling {name}: {e}"

    def openai_functions(self) -> List[Dict]:
        """Return OpenAI function-calling tool definitions."""
        return [{"type": "function", "function": {
            "name": t["name"], "description": t["desc"], "parameters": t["params"],
        }} for t in TOOL_DEFS]

    def _read(self, file_path="", path="", **kw) -> str:
        p = Path(file_path or path).expanduser()
        if not p.exists(): return f"Error: not found: {p}"
        try: return p.read_text(encoding="utf-8")[:10000]
        except Exception as e: return f"Error: {e}"

    def _write(self, file_path="", path="", content="", **kw) -> str:
        p = Path(file_path or path).expanduser()
        try: p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content, encoding="utf-8"); return f"Written: {p}"
        except Exception as e: return f"Error: {e}"

    def _edit(self, file_path="", path="", old_string="", new_string="", **kw) -> str:
        p = Path(file_path or path).expanduser()
        if not p.exists(): return f"Error: not found: {p}"
        text = p.read_text(encoding="utf-8")
        if old_string not in text: return "Error: old_string not found"
        p.write_text(text.replace(old_string, new_string, 1), encoding="utf-8"); return f"Edited: {p}"

    def _exec(self, command="", **kw) -> str:
        if self.security.is_dangerous(command): return f"Blocked: {command}"
        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return ((r.stdout + r.stderr).strip() or "(no output)")[:5000]
        except subprocess.TimeoutExpired: return "Error: timeout"
        except Exception as e: return f"Error: {e}"

    def _memory_search(self, query="", **kw) -> str:
        if not self.memory: return "Error: memory not configured"
        results = self.memory.memory_search(query)
        if not results: return "No results found"
        return "\n".join(f"[{r['file']}:{r['line']}] {r['content']}" for r in results[:5])

    def _memory_get(self, file_path="", start_line=1, end_line=0, **kw) -> str:
        if not self.memory: return "Error: memory not configured"
        return self.memory.memory_get(file_path, int(start_line), int(end_line))
# ─── xiaoclaw Core ────────────────────────────────────
class XiaClaw:
    def __init__(self, config: Optional[XiaClawConfig] = None):
        self.config = config or XiaClawConfig.from_env()
        self.workspace = Path(self.config.workspace)
        self.security = SecurityManager(self.config.security_level)
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

    async def _agent_loop(self, sys_prompt: str, stream: bool = False):
        """Core agent loop: LLM → tool calls → repeat. Yields chunks if stream=True."""
        max_rounds = 10
        client = self.providers.active.client
        model = self.providers.active.current_model

        for _ in range(max_rounds):
            ctx = self.session.get_context_window(self.config.max_context_tokens)
            all_msgs = [{"role": "system", "content": sys_prompt}] + ctx

            try:
                if stream:
                    # Non-streaming call for tool-calling rounds, stream only final text
                    resp = await client.chat.completions.create(
                        model=model, messages=all_msgs,
                        tools=self.tools.openai_functions(), max_tokens=2000,
                    )
                else:
                    resp = await client.chat.completions.create(
                        model=model, messages=all_msgs,
                        tools=self.tools.openai_functions(), max_tokens=2000,
                    )
            except Exception as e:
                logger.error(f"LLM error: {e}")
                yield f"[LLM Error: {e}]"; return

            choice = resp.choices[0]

            if choice.message.tool_calls:
                tc_msg = {"role": "assistant", "content": choice.message.content or "",
                          "tool_calls": [{"id": tc.id, "type": "function",
                                          "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                         for tc in choice.message.tool_calls]}
                self.session.add_message(**tc_msg)

                for tc in choice.message.tool_calls:
                    name = tc.function.name
                    try: args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError: args = {}

                    await self.hooks.fire("before_tool_call", tool=name, args=args)
                    result = self.tools.call(name, args)
                    await self.hooks.fire("after_tool_call", tool=name, args=args, result=result)
                    logger.info(f"Tool: {name}({list(args.keys())}) → {len(result)} chars")
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

    async def handle_message(self, message: str) -> str:
        """Process a user message, return full response."""
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

    async def handle_message_stream(self, message: str):
        """Process a user message, yield streaming chunks."""
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

# ─── CLI ─────────────────────────────────────────────

async def main():
    import sys
    # Support --config path
    config_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--config" and i + 1 < len(sys.argv):
            config_path = sys.argv[i + 1]

    config = XiaClawConfig.from_yaml(config_path) if config_path else XiaClawConfig.from_env()
    claw = XiaClaw(config)
    p = claw.providers.active
    print(f"\n  xiaoclaw v{VERSION} | {p.current_model if p else 'no LLM'} | session={claw.session.session_id}\n")

    if "--test" in sys.argv:
        print("--- Self Test ---")
        from .providers import test_providers; test_providers()
        from .session import test_session; test_session()
        from .memory import test_memory; test_memory()
        from .skills import test_skills; test_skills()
        from .web import test_web; test_web()
        for msg in ["你好", "工具列表", "1+1等于几？"]:
            r = await claw.handle_message(msg)
            print(f"  > {msg}\n  < {r[:200]}\n")
        print("  ✓ All tests passed!"); return

    CMDS = {
        "/help": lambda: print("  /tools /skills /model /sessions /memory /clear /quit"),
        "/tools": lambda: print(f"  {', '.join(claw.tools.list_names())}"),
        "/memory": lambda: print(f"  MEMORY.md: {len(claw.memory.read_memory())} chars"),
        "/clear": lambda: (setattr(claw, 'session', claw.session_mgr.new_session()), print("  New session")),
    }
    print("─" * 50)
    while True:
        try: user_input = input("\n🧑 You: ").strip()
        except (KeyboardInterrupt, EOFError): print("\nBye!"); break
        if not user_input: continue
        cmd = user_input.lower()
        if cmd in ("/quit", "/exit", "/q"): claw.session.save(); print("Bye!"); break
        if cmd in CMDS: CMDS[cmd](); continue
        if cmd == "/skills":
            for n in claw.skills.list_skills(): print(f"  {n}: {list(claw.skills.get_skill(n).tools.keys())}")
            continue
        if cmd == "/model":
            for pi in claw.providers.list_providers(): print(f"  {'→' if pi['active'] else ' '} {pi['name']}: {pi['model']}")
            continue
        if cmd == "/sessions":
            for s in claw.session_mgr.list_sessions(): print(f"  {s['session_id']} ({s['size']}B)")
            continue
        print(f"\n🐾 xiaoclaw: ", end="", flush=True)
        async for chunk in claw.handle_message_stream(user_input):
            print(chunk, end="", flush=True)
        print()  # newline after stream

if __name__ == "__main__":
    asyncio.run(main())
