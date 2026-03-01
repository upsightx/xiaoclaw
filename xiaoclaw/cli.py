"""xiaoclaw CLI — interactive terminal with setup wizard & slash completion"""
import sys
import os
import logging
import asyncio
import readline
from pathlib import Path

from .core import XiaClaw, XiaClawConfig, VERSION
from .battle import BattleEngine, PRESET_ROLES, DEFAULT_BATTLE_ROLES, list_preset_roles, format_battle_output

# ── Slash command registry ────────────────────────────────────
SLASH_COMMANDS = {
    "/help":          "显示帮助",
    "/tools":         "列出所有工具",
    "/skills":        "列出所有技能",
    "/skill":         "启用/禁用技能 (/skill on|off <name>)",
    "/model":         "查看Provider和模型",
    "/sessions":      "列出历史会话",
    "/restore":       "恢复会话 (/restore <id>)",
    "/memory":        "查看记忆状态",
    "/stats":         "Token使用统计",
    "/clear":         "新建会话",
    "/export":        "导出会话 (/export md|json)",
    "/loglevel":      "设置日志级别",
    "/reload":        "热重载配置",
    "/battle":        "多角色辩论 (/battle <问题>)",
    "/battle-roles":  "查看预设角色",
    "/battle-custom": "自定义角色辩论",
    "/analytics":     "Token统计分析 (/analytics [天数] 7/30)",
    "/version":       "查看版本",
    "/setup":         "重新运行设置向导",
    "/quit":          "退出",
}
ALIASES = {"/q": "/quit", "/h": "/help", "/t": "/tools", "/s": "/sessions",
           "/m": "/memory", "/c": "/clear", "/a": "/analytics", "/v": "/version", "/exit": "/quit"}

# ── Tab completion ────────────────────────────────────────────
class SlashCompleter:
    def __init__(self):
        self.matches = []

    def complete(self, text, state):
        if state == 0:
            line = readline.get_line_buffer().lstrip()
            if line.startswith("/"):
                all_cmds = list(SLASH_COMMANDS.keys()) + list(ALIASES.keys())
                self.matches = [c + " " for c in sorted(set(all_cmds)) if c.startswith(line)]
            else:
                self.matches = []
        return self.matches[state] if state < len(self.matches) else None


def _setup_readline():
    """Configure readline for slash command completion."""
    comp = SlashCompleter()
    readline.set_completer(comp.complete)
    readline.set_completer_delims(" \t\n")
    # macOS uses libedit
    if "libedit" in (readline.__doc__ or ""):
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")


# ── Setup wizard ──────────────────────────────────────────────
CONFIG_FILE = Path.home() / ".xiaoclaw" / "config.env"

PROVIDER_PRESETS = {
    "1": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": "gpt-4o, gpt-4o-mini, gpt-3.5-turbo",
        "default_model": "gpt-4o",
    },
    "2": {
        "name": "Claude (Anthropic)",
        "base_url": "https://api.anthropic.com/v1",
        "models": "claude-sonnet-4-20250514, claude-opus-4-20250514",
        "default_model": "claude-sonnet-4-20250514",
    },
    "3": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": "deepseek-chat, deepseek-reasoner",
        "default_model": "deepseek-chat",
    },
    "4": {
        "name": "自定义 (OpenAI兼容)",
        "base_url": "",
        "models": "",
        "default_model": "",
    },
}


def _run_setup_wizard() -> XiaClawConfig:
    """Interactive first-run setup wizard. Returns config."""
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║   🐾 xiaoclaw 首次设置向导           ║")
    print("  ╚══════════════════════════════════════╝")
    print()
    print("  选择你的 LLM 服务商：")
    print()
    for k, v in PROVIDER_PRESETS.items():
        print(f"    {k}. {v['name']}")
        if v["models"]:
            print(f"       模型: {v['models']}")
    print()

    choice = ""
    while choice not in PROVIDER_PRESETS:
        try:
            choice = input("  选择 (1-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  已取消"); sys.exit(0)

    preset = PROVIDER_PRESETS[choice]
    base_url = preset["base_url"]
    default_model = preset["default_model"]

    if choice == "4":
        print()
        print("  输入 OpenAI 兼容的 API 地址")
        print("  例如: https://api.openai.com/v1")
        try:
            base_url = input("  API地址: ").strip()
            default_model = input("  模型名称: ").strip() or "gpt-4o"
        except (KeyboardInterrupt, EOFError):
            print("\n  已取消"); sys.exit(0)
    else:
        print(f"\n  已选择: {preset['name']}")
        print(f"  可用模型: {preset['models']}")
        try:
            custom_model = input(f"  模型 (回车用 {default_model}): ").strip()
            if custom_model:
                default_model = custom_model
        except (KeyboardInterrupt, EOFError):
            print("\n  已取消"); sys.exit(0)

    print()
    try:
        api_key = input("  API Key: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n  已取消"); sys.exit(0)

    if not api_key:
        print("  ⚠ 未输入 API Key，将以离线模式运行")
        print()
        return XiaClawConfig.from_env()

    # Test connection
    print()
    print("  🔄 测试连接...", end="", flush=True)
    import asyncio as _aio
    from openai import AsyncOpenAI

    async def _test():
        try:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            resp = await client.chat.completions.create(
                model=default_model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return None, str(e)

    result = _aio.run(_test())
    if isinstance(result, str):
        print(f" ✅ 成功！({default_model})")
    else:
        err = result[1] if isinstance(result, tuple) else str(result)
        print(f" ❌ 失败: {err[:80]}")
        print()
        try:
            retry = input("  继续保存配置？(y/n): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n  已取消"); sys.exit(0)
        if retry != "y":
            return XiaClawConfig.from_env()

    # Save config
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        f"OPENAI_API_KEY={api_key}\n"
        f"OPENAI_BASE_URL={base_url}\n"
        f"XIAOCLAW_MODEL={default_model}\n",
        encoding="utf-8",
    )
    CONFIG_FILE.chmod(0o600)
    print(f"\n  ✅ 配置已保存到 {CONFIG_FILE}")
    print(f"     API: {base_url}")
    print(f"     模型: {default_model}")
    print()

    # Set env vars for this session
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_BASE_URL"] = base_url
    os.environ["XIAOCLAW_MODEL"] = default_model

    return XiaClawConfig.from_env()


def _load_saved_config():
    """Load config from ~/.xiaoclaw/config.env if exists."""
    if not CONFIG_FILE.exists():
        return False
    for line in CONFIG_FILE.read_text(encoding="utf-8").strip().split("\n"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            if key.strip() and val.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = val.strip()
    return True


def _needs_setup() -> bool:
    """Check if setup wizard should run."""
    # Has explicit env var
    if os.environ.get("OPENAI_API_KEY"):
        return False
    # Has saved config
    if CONFIG_FILE.exists():
        _load_saved_config()
        return not os.environ.get("OPENAI_API_KEY")
    # Check if core.py has a non-empty default key hardcoded (developer mode)
    try:
        from .core import XiaClawConfig
        cfg = XiaClawConfig()
        if cfg.api_key and len(cfg.api_key) > 10:
            return False
    except Exception:
        pass
    return True


# ── Session memory save ──────────────────────────────────────
async def _save_session_memory(claw):
    try:
        msgs = claw.session.messages
        if len(msgs) < 2:
            return
        from datetime import datetime
        entries = []
        for msg in msgs:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip() and not content.startswith("/"):
                    entries.append(f"- User: {content[:100]}")
        if entries:
            summary = f"## Session Summary\n" + "\n".join(entries[:10])
            claw.memory.append_daily(summary)
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────
async def main():
    if "--web" in sys.argv or "--webui" in sys.argv:
        _load_saved_config()
        config = XiaClawConfig.from_yaml(config_path) if config_path else XiaClawConfig.from_env()
        _run_webui(config)
        return


        print(f"xiaoclaw v{VERSION} — Lightweight AI Agent")
        print(f"  xiaoclaw              交互模式")
        print(f"  xiaoclaw --setup      运行设置向导")
        print(f"  xiaoclaw --debug      调试模式")
        print(f"  xiaoclaw --web        启动 Web UI")
        print(f"  xiaoclaw --test       自检测试")
        print(f"  xiaoclaw --config X   指定配置文件")
        return

    # Load saved config first
    _load_saved_config()

    # Config path override
    config_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--config" and i + 1 < len(sys.argv):
            config_path = sys.argv[i + 1]

    # Setup wizard
    if "--setup" in sys.argv or _needs_setup():
        config = _run_setup_wizard()
    else:
        config = XiaClawConfig.from_yaml(config_path) if config_path else XiaClawConfig.from_env()

    # Logging
    if "--debug" in sys.argv:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("xiaoclaw").setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.INFO)
    else:
        for name in ("", "xiaoclaw", "httpx", "httpcore", "openai"):
            logging.getLogger(name).setLevel(logging.WARNING)

    for i, arg in enumerate(sys.argv):
        if arg == "--log-level" and i + 1 < len(sys.argv):
            lvl = sys.argv[i + 1].upper()
            if lvl in ("DEBUG", "INFO", "WARNING", "ERROR"):
                logging.getLogger().setLevel(getattr(logging, lvl))

    claw = XiaClaw(config)
    p = claw.providers.active
    model_name = p.current_model if p else "no LLM"
    ready = "✓" if (p and p.ready) else "✗"
    print(f"\n  🐾 xiaoclaw v{VERSION} | {model_name} {ready}\n")

    if "--test" in sys.argv:
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger("xiaoclaw").setLevel(logging.INFO)
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

    # Setup readline completion
    _setup_readline()

    # Show quick help on first run
    if not (Path.home() / ".xiaoclaw" / ".welcomed").exists():
        print("  💡 输入 / 然后按 Tab 查看所有命令")
        print("  💡 输入 /setup 重新配置 API")
        print("  💡 输入 /help 查看帮助")
        print()
        (Path.home() / ".xiaoclaw").mkdir(parents=True, exist_ok=True)
        (Path.home() / ".xiaoclaw" / ".welcomed").touch()

    # ── Command handlers ──────────────────────────────
    def cmd_help():
        print("\n  📋 可用命令:\n")
        for cmd, desc in SLASH_COMMANDS.items():
            print(f"    {cmd:18s} {desc}")
        print()

    SIMPLE_CMDS = {
        "/help": cmd_help,
        "/tools": lambda: print(f"  🔧 {', '.join(claw.tools.list_names())}"),
        "/memory": lambda: print(f"  🧠 MEMORY.md: {len(claw.memory.read_memory())} chars"),
        "/clear": lambda: (setattr(claw, 'session', claw.session_mgr.new_session()), print("  ✨ 新会话已创建")),
        "/stats": lambda: print(f"  📊 {claw.stats.summary()}"),
        "/version": lambda: print(f"  🐾 xiaoclaw v{VERSION}"),
        "/battle-roles": lambda: print(list_preset_roles()),
    }

    # ── Main loop ─────────────────────────────────────
    print("─" * 50)
    while True:
        try:
            user_input = input("\n🧑 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            await _save_session_memory(claw)
            print("\nBye!")
            break
        except UnicodeDecodeError:
            print("  ⚠ 输入编码错误，请重新输入")
            continue
        if not user_input:
            continue

        cmd = user_input.lower().split()[0] if user_input.startswith("/") else ""
        cmd = ALIASES.get(cmd, cmd)

        # Quit
        if cmd in ("/quit",):
            claw.session.save()
            await _save_session_memory(claw)
            print("Bye!"); break

        # Simple commands
        if cmd in SIMPLE_CMDS:
            SIMPLE_CMDS[cmd](); continue

        # Setup wizard
        if cmd == "/setup":
            _run_setup_wizard()
            claw = XiaClaw(XiaClawConfig.from_env())
            p = claw.providers.active
            model_name = p.current_model if p else "no LLM"
            ready = "✓" if (p and p.ready) else "✗"
            print(f"\n  🐾 xiaoclaw v{VERSION} | {model_name} {ready}\n")
            continue

        # Skills
        if cmd == "/skills":
            for n in claw.skills.list_skills():
                sk = claw.skills.get_skill(n)
                status = "✓" if sk.active else "○"
                print(f"  {status} {n}: {list(sk.tools.keys())}")
            continue
        if cmd == "/skill":
            parts = user_input.split()
            if len(parts) >= 3:
                action, sname = parts[1].lower(), parts[2]
                sk = claw.skills.get_skill(sname)
                if sk:
                    sk.active = action == "on"
                    print(f"  {sname}: {'✓ 已启用' if sk.active else '○ 已禁用'}")
                else:
                    print(f"  ❌ 技能不存在: {sname}")
            else:
                print("  用法: /skill on|off <name>")
            continue

        # Model
        if cmd == "/model":
            for pi in claw.providers.list_providers():
                print(f"  {'→' if pi['active'] else ' '} {pi['name']}: {pi['model']}")
            continue

        # Sessions
        if cmd == "/sessions":
            sessions = claw.session_mgr.list_sessions()
            if sessions:
                for s in sessions:
                    print(f"  📝 {s['session_id']} ({s['size']}B)")
            else:
                print("  (无历史会话)")
            continue
        if cmd == "/restore":
            parts = user_input.split()
            if len(parts) >= 2:
                sid = parts[1]
                restored = claw.session_mgr.restore(sid)
                if restored:
                    claw.session = restored
                    print(f"  ✅ 已恢复会话 {sid} ({len(restored.messages)} 条消息)")
                else:
                    print(f"  ❌ 会话不存在: {sid}")
            else:
                print("  用法: /restore <session_id>")
            continue

        # Export
        if cmd == "/export":
            parts = user_input.split()
            fmt = parts[1] if len(parts) >= 2 else "md"
            msgs = claw.session.messages
            if "json" in fmt:
                import json
                out = json.dumps(msgs, ensure_ascii=False, indent=2)
                ext = "json"
            else:
                lines = [f"# Session {claw.session.session_id}\n"]
                for m in msgs:
                    role = m.get("role", "?")
                    content = m.get("content", "")
                    if isinstance(content, str) and content.strip():
                        lines.append(f"**{role}**: {content}\n")
                out = "\n".join(lines)
                ext = "md"
            path = f"/tmp/xiaoclaw_export_{claw.session.session_id}.{ext}"
            Path(path).write_text(out, encoding="utf-8")
            print(f"  📄 已导出到 {path}")
            continue

        # Log level
        if cmd == "/loglevel":
            parts = user_input.split()
            if len(parts) >= 2:
                lvl = parts[1].upper()
                if lvl in ("DEBUG", "INFO", "WARNING", "ERROR"):
                    logging.getLogger().setLevel(getattr(logging, lvl))
                    print(f"  日志级别: {lvl}")
                else:
                    print("  可选: DEBUG INFO WARNING ERROR")
            else:
                print(f"  当前: {logging.getLevelName(logging.getLogger().level)}")
            continue

        # Reload
        if cmd == "/reload":
            ok = claw.reload_config(config_path or "config.yaml")
            print(f"  {'✅ 配置已重载' if ok else '❌ 重载失败'}")
            continue

        # Battle
        if cmd == "/battle-custom":
            parts = user_input.split(None, 2)
            if len(parts) < 3:
                print("  用法: /battle-custom <角色1,角色2,...> <问题>")
                print(f"  可用角色: {', '.join(PRESET_ROLES.keys())}")
                continue
            role_str, question = parts[1], parts[2]
            role_keys = [r.strip() for r in role_str.split(",") if r.strip()]
            p = claw.providers.active
            if not (p and p.ready):
                print("  ❌ LLM未配置"); continue
            print(f"\n  🏢 Battle开始... (角色: {', '.join(role_keys)})\n")
            engine = BattleEngine(p)
            result = await engine.battle(question, role_keys=role_keys)
            print(result["formatted"])
            continue
        if cmd == "/battle":
            question = user_input[len("/battle"):].strip()
            if not question:
                print("  用法: /battle <问题>")
                print(f"  默认角色: {', '.join(DEFAULT_BATTLE_ROLES)}")
                continue
            p = claw.providers.active
            if not (p and p.ready):
                print("  ❌ LLM未配置"); continue
            print(f"\n  🏢 Battle开始... (角色: {', '.join(DEFAULT_BATTLE_ROLES)})\n")
            engine = BattleEngine(p)
            result = await engine.battle(question)
            print(result["formatted"])
            continue

        # Unknown slash command
        if user_input.startswith("/") and cmd not in SLASH_COMMANDS:
            close = [c for c in SLASH_COMMANDS if c.startswith(cmd[:3])]
            if close:
                print(f"  ❓ 未知命令。你是不是想输入: {', '.join(close)}")
            else:
                print(f"  ❓ 未知命令。输入 /help 查看所有命令")
            continue

        # ── Normal message → LLM ──────────────────────
        print(f"\n🐾 xiaoclaw: ", end="", flush=True)
        async for chunk in claw.handle_message_stream(user_input):
            print(chunk, end="", flush=True)
        print()


def _cli_entry():
    """Entry point for `xiaoclaw` console command."""
    asyncio.run(main())

def _run_webui(config):
    """Run Web UI mode."""
    from .webui import run_webui
    print(f"\n  🌐 启动 Web UI...\n")
    run_webui(host="0.0.0.0", port=8080)
