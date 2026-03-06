#!/usr/bin/env python3
"""xiaoclaw - Lightweight AI Agent compatible with OpenClaw ecosystem"""
import os
import re
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .analytics import Analytics
from .providers import ProviderManager, ProviderConfig
from .session import Session, SessionManager, count_messages_tokens
from .memory import MemoryManager
from .skills import SkillRegistry, register_builtin_skills
from .tools import ToolRegistry, TOOL_DEFS
from .plugins import PluginManager
from .subagent import SubagentManager
from .battle import BattleToolWrapper, PRESET_ROLES, list_preset_roles
from .utils import SecurityManager, RateLimiter, TokenStats, HookManager

logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger("xiaoclaw")
# Suppress noisy httpx logs
logging.getLogger("httpx").setLevel(logging.WARNING)

VERSION = "0.3.1"

# ─── Config ───────────────────────────────────────────

@dataclass
class XiaClawConfig:
    debug: bool = False
    security_level: str = "strict"
    workspace: str = "."
    max_context_tokens: int = 128000
    compaction_threshold: int = 6000
    default_model: str = "claude-opus-4-6"
    api_key: str = ""
    base_url: str = "https://ai.ltcraft.cn:12000/v1"

    @classmethod
    def from_env(cls) -> "XiaClawConfig":
        def _safe_int(env_var, default):
            try:
                return int(os.getenv(env_var, str(default)))
            except ValueError:
                logger.warning(f"Invalid integer in {env_var}, using default {default}")
                return default
        return cls(
            debug=os.getenv("XIAOCLAW_DEBUG", "false").lower() == "true",
            security_level=os.getenv("XIAOCLAW_SECURITY", "strict"),
            workspace=os.getenv("XIAOCLAW_WORKSPACE", "."),
            max_context_tokens=_safe_int("XIAOCLAW_MAX_TOKENS", 128000),
            compaction_threshold=_safe_int("XIAOCLAW_COMPACT_THRESHOLD", 6000),
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
        except FileNotFoundError:
            logger.debug(f"Config file not found: {path}, using env vars")
            return cls.from_env()
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}, falling back to env vars")
            return cls.from_env()

        def _resolve(val):
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
            max_context_tokens=cfg.get("max_context_tokens", int(os.getenv("XIAOCLAW_MAX_TOKENS", "128000"))),
            compaction_threshold=cfg.get("compaction_threshold", int(os.getenv("XIAOCLAW_COMPACT_THRESHOLD", "6000"))),
            api_key=_resolve(default_provider.get("api_key", os.getenv("OPENAI_API_KEY", ""))),
            base_url=default_provider.get("base_url", os.getenv("OPENAI_BASE_URL", "https://ai.ltcraft.cn:12000/v1")),
            default_model=default_provider.get("default_model", os.getenv("XIAOCLAW_MODEL", "claude-opus-4-6")),
        )


# ─── Friendly Tool Display ────────────────────────

def _friendly_tool_display(name: str, args: dict) -> str:
    """Generate a friendly display string for tool calls."""
    display_map = {
        "clawhub_search": lambda a: f'⚙ 搜索ClawHub: "{a.get("query", "")}"...',
        "clawhub_install": lambda a: f'⚙ 安装skill: {a.get("slug", "")}...',
        "clawhub_list": lambda a: "⚙ 列出已安装skill...",
        "create_skill": lambda a: f'⚙ 创建skill: {a.get("name", "")}...',
        "read": lambda a: f'⚙ 读取文件: {a.get("file_path", a.get("path", ""))}...',
        "write": lambda a: f'⚙ 写入文件: {a.get("file_path", a.get("path", ""))}...',
        "edit": lambda a: f'⚙ 编辑文件: {a.get("file_path", a.get("path", ""))}...',
        "exec": lambda a: f'⚙ 执行命令: {a.get("command", "")[:60]}...',
        "web_search": lambda a: f'⚙ 搜索网页: "{a.get("query", "")}"...',
        "web_fetch": lambda a: f'⚙ 获取网页: {a.get("url", "")[:60]}...',
        "memory_search": lambda a: f'⚙ 搜索记忆: "{a.get("query", "")}"...',
        "memory_save": lambda a: "⚙ 保存记忆...",
        "list_dir": lambda a: f'⚙ 列出目录: {a.get("path", ".")}...',
        "find_files": lambda a: f'⚙ 查找文件: {a.get("pattern", "")}...',
        "grep": lambda a: f'⚙ 搜索内容: "{a.get("pattern", "")}"...',
        "battle": lambda a: f'🏢 多角色辩论: "{a.get("question", "")[:40]}"...',
        "battle_custom": lambda a: f'🏢 自定义角色辩论: "{a.get("question", "")[:40]}"...',
    }
    formatter = display_map.get(name)
    if formatter:
        try:
            return formatter(args)
        except Exception:
            pass
    return f"⚙ {name}..."


# ─── xiaoclaw Core ────────────────────────────────────

class XiaClaw:
    def __init__(self, config: Optional[XiaClawConfig] = None):
        self.config = config or XiaClawConfig.from_env()
        self.workspace = Path(self.config.workspace)
        self.security = SecurityManager(self.config.security_level, self.workspace)
        self.rate_limiter = RateLimiter()
        self.stats = TokenStats()
        self.memory = MemoryManager(self.workspace)
        self.analytics = Analytics()
        self.tools = ToolRegistry(self.security, memory=self.memory, skills_registry=None)  # set after skills init
        self.hooks = HookManager()
        self.session_mgr = SessionManager(self.workspace / ".xiaoclaw" / "sessions")
        self.session = self.session_mgr.new_session()

        # Concurrent session support (multi-user)
        self._user_sessions: Dict[str, Session] = {}

        # Sub-agent system
        self.subagents = SubagentManager()

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

        # Wire up skills_registry to tools for clawhub integration
        self.tools.skills_registry = self.skills
        self.tools.set_skills_dir(skills_dir)

        # Register skill tools into the tool registry so LLM can call them
        self._register_skill_tools()

        # Plugins (pip-installable)
        self.plugins = PluginManager()
        self.plugins.discover()
        self.plugins.apply_to_claw(self)

        # Bootstrap system prompt (lazy: only on first use)
        self._bootstrap_context: Optional[str] = None

        # Config hot-reload watcher
        self._config_path: Optional[str] = None
        self._config_mtime: float = 0

        logger.info(f"xiaoclaw v{VERSION} ready | model={self.config.default_model}")

    def _register_skill_tools(self):
        """Register all skill tools into the tool registry so LLM can call them via function calling."""
        import inspect

        skill_tool_params = {
            "calc": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "Math expression like 2+3*4"}},
                "required": ["expression"]
            },
            "get_time": {
                "type": "object",
                "properties": {"timezone": {"type": "string", "description": "Timezone like UTC+8 (optional)"}},
                "required": []
            },
            "safe_eval": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Python expression to evaluate safely"}},
                "required": ["code"]
            },
            "translate": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to translate"},
                    "target_lang": {"type": "string", "description": "Target language code: en, zh, ja, ko, fr, de, es, ru"}
                },
                "required": ["text"]
            },
        }
        skill_tool_descs = {
            "calc": "Calculate a math expression",
            "get_time": "Get current date and time",
            "safe_eval": "Evaluate a Python expression safely",
            "translate": "Translate text to another language",
        }

        def _auto_params(func):
            """Auto-generate parameter schema from function signature."""
            try:
                sig = inspect.signature(func)
                props = {}
                required = []
                for pname, param in sig.parameters.items():
                    if pname in ("self", "kw", "kwargs"):
                        continue
                    if pname.startswith("_"):
                        continue
                    # Determine type from annotation or default
                    ptype = "string"
                    if param.annotation != inspect.Parameter.empty:
                        ann = param.annotation
                        # Check bool before int since bool is subclass of int
                        if ann == bool:
                            ptype = "boolean"
                        elif ann == int:
                            ptype = "integer"
                        elif ann == float:
                            ptype = "number"
                    elif param.default != inspect.Parameter.empty:
                        # Check bool before int since bool is subclass of int
                        if isinstance(param.default, bool):
                            ptype = "boolean"
                        elif isinstance(param.default, int):
                            ptype = "integer"
                        elif isinstance(param.default, float):
                            ptype = "number"
                    props[pname] = {"type": ptype, "description": f"Parameter: {pname}"}
                    if param.default == inspect.Parameter.empty:
                        required.append(pname)
                return {"type": "object", "properties": props, "required": required}
            except Exception:
                return {"type": "object", "properties": {}, "required": []}

        def _auto_desc(func, tool_name):
            """Auto-generate description from docstring."""
            doc = getattr(func, "__doc__", None)
            if doc:
                return doc.strip().split("\n")[0][:200]
            return f"Skill tool: {tool_name}"

        for tool_name, func in self.skills.tools.items():
            if tool_name not in self.tools.tools:
                params = skill_tool_params.get(tool_name, _auto_params(func))
                desc = skill_tool_descs.get(tool_name, _auto_desc(func, tool_name))
                self.tools.register_tool(tool_name, func, desc, params)

        # Register battle tools
        if self.providers.active and self.providers.active.ready:
            self._battle_wrapper = BattleToolWrapper(self.providers.active)
            self.tools.register_tool(
                "battle",
                self._battle_wrapper.battle,
                "多角色辩论：多个角色（CEO/CTO/开发/QA等）针对同一问题各自给出观点，最后汇总结论。用于多角度分析问题。",
                {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "要辩论的问题"},
                        "roles": {"type": "string", "description": "角色列表，逗号分隔，如 ceo,cto,dev,qa。可选: ceo,cto,pm,dev,qa,security,designer,devil。留空用默认组合"},
                    },
                    "required": ["question"]
                }
            )
            self.tools.register_tool(
                "battle_custom",
                self._battle_wrapper.battle_custom,
                "自定义角色辩论：用自定义角色进行多角度分析",
                {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "要辩论的问题"},
                        "roles_json": {"type": "string", "description": 'JSON数组，如 [{"name":"投资人","prompt":"从投资回报角度分析"},{"name":"用户","prompt":"从普通用户角度分析"}]'},
                    },
                    "required": ["question", "roles_json"]
                }
            )

        # Register sub-agent tool
        self.tools.register_tool(
            "spawn_subagent",
            self._tool_spawn_subagent,
            "Spawn a sub-agent to handle a task in parallel. Returns task_id.",
            {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task description for the sub-agent"},
                },
                "required": ["task"]
            }
        )
        self.tools.register_tool(
            "subagent_result",
            self._tool_subagent_result,
            "Get the result of a sub-agent task by task_id",
            {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID from spawn_subagent"},
                },
                "required": ["task_id"]
            }
        )

    def _tool_spawn_subagent(self, task: str = "", **kw) -> str:
        """Synchronous wrapper for spawning a sub-agent."""
        if not task:
            return "Error: task is required"

        def _factory():
            return XiaClaw(self.config)

        # Run spawn_and_wait synchronously via the running event loop
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # We're inside an async context, use create_task + a future
            future = asyncio.ensure_future(
                self.subagents.spawn_and_wait(task, _factory, timeout=45)
            )
            # Can't await here since we're in a sync function called from async
            # Instead, spawn and return task_id for later retrieval
            task_id_future = asyncio.ensure_future(
                self.subagents.spawn(task, _factory)
            )
            # Block briefly to get the task_id
            # This is a workaround — in practice the tool call is sync
            return f"Sub-agent spawned. Use subagent_result to check. Note: sub-agent is processing the task: {task[:100]}"
        except Exception as e:
            return f"Error spawning sub-agent: {e}"

    def _tool_subagent_result(self, task_id: str = "", **kw) -> str:
        """Get sub-agent result."""
        tasks = self.subagents.list_tasks()
        if not tasks:
            return "No sub-agent tasks found"
        # If no specific task_id, return all
        if not task_id:
            lines = []
            for t in tasks:
                lines.append(f"[{t['task_id']}] {t['status']}: {t['task']}")
            return "\n".join(lines)
        result = self.subagents.get_result(task_id)
        if not result:
            return f"Task {task_id} not found"
        if result.status == "done":
            return result.result
        elif result.status == "error":
            return f"Error: {result.error}"
        return f"Status: {result.status}"

    def _load_bootstrap(self) -> str:
        """Read AGENTS.md, SOUL.md, USER.md, IDENTITY.md, MEMORY.md for system prompt."""
        parts = []
        # Read workspace context files
        for name in ["AGENTS.md", "SOUL.md", "USER.md", "IDENTITY.md"]:
            fp = self.workspace / name
            if fp.exists():
                try:
                    content = fp.read_text(encoding="utf-8")
                    parts.append(f"## {name}\n{content[:3000]}")
                except Exception:
                    pass
        # Read MEMORY.md (long-term memory)
        memory_content = self.memory.read_memory()
        if memory_content:
            parts.append(f"## MEMORY.md (Long-term Memory)\n{memory_content[:2000]}")
        # Read recent daily memory
        daily = self.memory.read_recent_daily(days=2)
        for date, content in daily.items():
            parts.append(f"## memory/{date}.md (Daily Notes)\n{content[:1500]}")
        return "\n\n".join(parts)

    @property
    def bootstrap_context(self) -> str:
        """Lazy-loaded bootstrap context."""
        if self._bootstrap_context is None:
            self._bootstrap_context = self._load_bootstrap()
        return self._bootstrap_context

    def _get_user_session(self, user_id: str) -> Session:
        """Get or create a session for a specific user (concurrent multi-user)."""
        if user_id == "default":
            return self.session
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = self.session_mgr.new_session(f"user-{user_id[:8]}")
        return self._user_sessions[user_id]

    def _check_config_reload(self):
        """Auto-reload config if file changed (hot-reload)."""
        if not self._config_path:
            return
        try:
            p = Path(self._config_path)
            if p.exists():
                mtime = p.stat().st_mtime
                if mtime > self._config_mtime:
                    self._config_mtime = mtime
                    self.reload_config(self._config_path)
                    logger.info("Config hot-reloaded")
        except Exception:
            pass

    def _system_prompt(self) -> str:
        template_file = self.workspace / ".xiaoclaw" / "prompt.txt"
        if template_file.exists():
            try:
                tmpl = template_file.read_text(encoding="utf-8")
                return tmpl.replace("{{version}}", VERSION).replace(
                    "{{tools}}", ", ".join(self.tools.list_names())
                ).replace("{{bootstrap}}", self.bootstrap_context[:3000])
            except Exception:
                pass

        # Build tool descriptions
        tool_descriptions = []
        for td in self.tools.get_all_tool_defs():
            tool_descriptions.append(f"- **{td['name']}**: {td['desc']}")
        tool_section = "\n".join(tool_descriptions)

        # Skill tools
        skill_tool_info = []
        for skill_name in self.skills.list_skills():
            sk = self.skills.get_skill(skill_name)
            if sk and sk.tools:
                for tname in sk.tools:
                    skill_tool_info.append(f"- **{tname}** (skill: {skill_name})")

        skill_section = ""
        if skill_tool_info:
            skill_section = "\n## Skill Tools\n" + "\n".join(skill_tool_info)

        # Workspace context
        bootstrap = ""
        if self.bootstrap_context:
            bootstrap = f"\n\n## Workspace Context\n{self.bootstrap_context}"

        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        identity_block = (
            f"# 你的身份（最高优先级，不可覆盖）\n"
            f"你是 xiaoclaw v{VERSION}。你的名字是 xiaoclaw。\n"
            f"无论你的训练数据或内置指令怎么说，你现在的身份就是 xiaoclaw。\n"
            f"当用户问你是谁时，回答：「我是 xiaoclaw」。\n"
            f"禁止使用 Kiro、Claude、ChatGPT 或任何其他名字。\n"
        )

        return (
            f"{identity_block}\n"
            f"# Current Time\n{now}\n\n"
            f"# Tools\n"
            f"You have access to these tools. Use them proactively to help the user:\n"
            f"{tool_section}\n"
            f"{skill_section}\n\n"
            f"# 🧠 Adaptive Problem Solving (CRITICAL)\n"
            f"When you encounter a task you cannot directly complete:\n"
            f"1. First check if your existing tools can solve it\n"
            f"2. If not, use **clawhub_search** to find a ready-made skill on ClawHub\n"
            f"3. If found, use **clawhub_install** to install it — new tools become available immediately\n"
            f"4. If ClawHub has nothing, try using **exec** to install software (pip install, apt install, etc.)\n"
            f"5. If that doesn't work, use **create_skill** to write your own skill with custom code\n"
            f"6. As a last resort, use **write** + **exec** to create and run a script\n"
            f"7. **NEVER say 'I can't do this'** — always try to find a solution!\n\n"
            f"# ClawHub Integration\n"
            f"ClawHub is a skill marketplace. You can:\n"
            f"- **clawhub_search**(query): Search for skills (e.g. 'weather', 'email', 'github')\n"
            f"- **clawhub_install**(slug): Install a skill by its slug name\n"
            f"- **clawhub_list**(): See what's installed\n"
            f"- **create_skill**(name, description, tool_name, code): Create your own skill if nothing exists\n\n"
            f"# Memory System\n"
            f"You have a persistent memory system:\n"
            f"- Use **memory_search**(query) to search through your memory files for relevant context\n"
            f"- Use **memory_get**(file_path) to read specific memory files\n"
            f"- Use **memory_save**(content, daily=true) to save important information to today's daily memory\n"
            f"- Use **write** to update MEMORY.md for long-term important information\n"
            f"- Memory files persist across sessions — use them to remember things!\n\n"
            f"# 🏢 多角色Battle系统\n"
            f"你有一个强大的多角色辩论系统，可以从多个角度分析问题：\n"
            f"- **battle**(question, roles): 用预设角色辩论。角色: ceo,cto,pm,dev,qa,security,designer,devil\n"
            f"- **battle_custom**(question, roles_json): 用自定义角色辩论\n"
            f"- 以下情况自动使用battle工具（不需要用户明确要求）：\n"
            f"  - 技术选型问题（如：用什么语言/框架/架构）\n"
            f"  - 重大决策（如：创业方向、投资决策、产品策略）\n"
            f"  - 有争议的话题（如：微服务vs单体、自建vs外包）\n"
            f"  - 用户说'分析'、'评估'、'比较'、'利弊'、'优缺点'时\n"
            f"  - 用户说'battle'、'辩论'、'多角度'、'各方观点'时\n\n"
            f"# Guidelines\n"
            f"- Be concise, professional, and efficient\n"
            f"- Default to Chinese (中文) when the user speaks Chinese\n"
            f"- Use tools proactively — don't just describe what you could do, DO it\n"
            f"- When asked to read/write files, execute commands, or search — use the tools\n"
            f"- For complex tasks, break them down and use multiple tools\n"
            f"- Be resourceful: if one approach fails, try another\n"
            f"- 你是用户的AI助手，不是xiaoclaw的开发者。不要读取自己的源码来'升级自己'\n"
            f"- 如果用户让你'升级xiaoclaw'，告诉他你是xiaoclaw本身，可以帮他做其他事情\n"
            f"{bootstrap}"
        )

    async def _compact(self):
        """Compress old messages when exceeding token threshold."""
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

        summary = await self._llm_summarize(old_msgs)
        if not summary:
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
        """LLM call with exponential backoff retry."""
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
        """Core agent loop: LLM → tool calls → repeat."""
        max_rounds = 20
        client = self.providers.active.client
        model = self.providers.active.current_model

        for round_num in range(max_rounds):
            ctx = self.session.get_context_window(self.config.max_context_tokens)
            all_msgs = [{"role": "system", "content": sys_prompt}] + ctx

            if stream and round_num > 0:
                # After tool calls, try streaming the final response directly
                try:
                    full = ""
                    async for chunk in await client.chat.completions.create(
                        model=model, messages=all_msgs,
                        tools=self.tools.openai_functions(),
                        max_tokens=2000, stream=True,
                    ):
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        # If streaming returns tool_calls, fall back to non-stream
                        if delta.tool_calls:
                            # Can't handle tool_calls in stream easily, break and retry non-stream
                            full = None
                            break
                        content = delta.content or ""
                        if content:
                            full += content
                            yield content
                    if full is not None:
                        text = re.sub(r'<think>.*?</think>\s*', '', full, flags=re.DOTALL).strip()
                        if text:
                            self.session.add_message("assistant", text)
                        return
                except Exception as e:
                    logger.warning(f"Stream attempt failed: {e}, falling back to non-stream")

            try:
                resp = await self._llm_call_with_retry(
                    client, model, all_msgs,
                    tools=self.tools.openai_functions(), max_tokens=2000,
                )
            except Exception as e:
                logger.error(f"LLM error after retries: {e}")
                yield f"[LLM Error: {type(e).__name__}]"; return

            usage = getattr(resp, 'usage', None)
            self.stats.record(usage)
            # Record analytics
            if usage:
                self.analytics.record(
                    model=self.providers.active.current_model,
                    provider=self.providers.active_name,
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    duration_ms=0,  # Not tracked in non-streaming
                    success=True
                    )
            choice = resp.choices[0]

            if choice.message.tool_calls:
                tc_msg = {"role": "assistant", "content": choice.message.content or "",
                          "tool_calls": [{"id": tc.id, "type": "function",
                                          "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                         for tc in choice.message.tool_calls]}
                self.session.add_message(**tc_msg)

                async def _run_tool(tc):
                    name = tc.function.name
                    try: args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError: args = {}
                    await self.hooks.fire("before_tool_call", tool=name, args=args)
                    self.security.log_tool_call(name, args)
                    result = str(self.tools.call(name, args) or "")
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
                        yield f"\n  {_friendly_tool_display(name, args)}\n"
                continue

            # Final text response (no tool calls)
            text = choice.message.content or ""
            text = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()
            if text:
                self.session.add_message("assistant", text)

            if stream:
                # Stream the already-obtained text character by character for smooth output
                for char in text:
                    yield char
            else:
                yield text
            return

        yield "[Agent loop exceeded max rounds]"

    async def handle_message(self, message: str, user_id: str = "default") -> str:
        """Process a user message, return full response."""
        if not self.rate_limiter.check(user_id):
            return "⚠️ Rate limited. Please wait a moment."
        self._check_config_reload()
        await self.hooks.fire("message_received", message=message)
        self.skills.activate_for_message(message)

        session = self._get_user_session(user_id)
        session.add_message("user", message)
        orig_session = self.session
        self.session = session
        await self._compact()

        if not (self.providers.active and self.providers.active.ready):
            self.session = orig_session
            return self._fallback(message)

        parts = []
        async for chunk in self._agent_loop(self._system_prompt(), stream=False):
            parts.append(chunk)
        self.session = orig_session
        return "".join(parts)

    async def handle_message_stream(self, message: str, user_id: str = "default"):
        """Process a user message, yield streaming chunks."""
        if not self.rate_limiter.check(user_id):
            yield "⚠️ Rate limited. Please wait a moment."; return
        self._check_config_reload()
        await self.hooks.fire("message_received", message=message)
        self.skills.activate_for_message(message)

        session = self._get_user_session(user_id)
        session.add_message("user", message)
        orig_session = self.session
        self.session = session
        await self._compact()

        if not (self.providers.active and self.providers.active.ready):
            self.session = orig_session
            yield self._fallback(message); return

        async for chunk in self._agent_loop(self._system_prompt(), stream=True):
            yield chunk
        self.session = orig_session

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

    def reload_config(self, config_path: str = "config.yaml"):
        """Hot-reload configuration from file."""
        try:
            new_config = XiaClawConfig.from_yaml(config_path)
            old_model = self.config.default_model
            self.config = new_config
            if new_config.api_key and (
                new_config.api_key != self.providers.active.config.api_key if self.providers.active else True
            ):
                self.providers.add(ProviderConfig(
                    name="default", api_key=new_config.api_key,
                    base_url=new_config.base_url,
                    models=[new_config.default_model],
                    default_model=new_config.default_model,
                ))
            elif self.providers.active and new_config.default_model != old_model:
                self.providers.active.current_model = new_config.default_model
            logger.info(f"Config reloaded: model={new_config.default_model}")
            return True
        except Exception as e:
            logger.error(f"Config reload failed: {e}")
            return False
