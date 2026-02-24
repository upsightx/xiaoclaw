"""xiaoclaw CLI — interactive terminal interface"""
import sys
import logging
import asyncio
from pathlib import Path

from .core import XiaClaw, XiaClawConfig, VERSION


async def _save_session_memory(claw):
    """Save important conversation info to daily memory on quit."""
    try:
        msgs = claw.session.messages
        if len(msgs) < 2:
            return
        # Extract key user messages for daily log
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


async def main():
    # Quick flags
    if "--version" in sys.argv or "-V" in sys.argv:
        print(f"xiaoclaw v{VERSION}"); return

    # Support --config path
    config_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--config" and i + 1 < len(sys.argv):
            config_path = sys.argv[i + 1]

    config = XiaClawConfig.from_yaml(config_path) if config_path else XiaClawConfig.from_env()

    # Default: WARNING level. --debug for verbose
    if "--debug" in sys.argv:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("xiaoclaw").setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("xiaoclaw").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)

    # Support --log-level override
    for i, arg in enumerate(sys.argv):
        if arg == "--log-level" and i + 1 < len(sys.argv):
            lvl = sys.argv[i + 1].upper()
            if lvl in ("DEBUG", "INFO", "WARNING", "ERROR"):
                logging.getLogger().setLevel(getattr(logging, lvl))

    claw = XiaClaw(config)
    p = claw.providers.active
    model_name = p.current_model if p else 'no LLM'
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

    CMDS = {
        "/help": lambda: print("  /tools /skills /skill /model /sessions /restore /memory /stats /clear /export /loglevel /quit"),
        "/tools": lambda: print(f"  {', '.join(claw.tools.list_names())}"),
        "/t": lambda: print(f"  {', '.join(claw.tools.list_names())}"),
        "/memory": lambda: print(f"  MEMORY.md: {len(claw.memory.read_memory())} chars"),
        "/m": lambda: print(f"  MEMORY.md: {len(claw.memory.read_memory())} chars"),
        "/clear": lambda: (setattr(claw, 'session', claw.session_mgr.new_session()), print("  New session")),
        "/c": lambda: (setattr(claw, 'session', claw.session_mgr.new_session()), print("  New session")),
        "/stats": lambda: print(f"  {claw.stats.summary()}"),
        "/version": lambda: print(f"  xiaoclaw v{VERSION}"),
        "/v": lambda: print(f"  xiaoclaw v{VERSION}"),
    }
    ALIASES = {"/q": "/quit", "/h": "/help", "/s": "/sessions"}

    def _export_session(fmt: str):
        msgs = claw.session.messages
        if fmt == "json":
            import json
            out = json.dumps(msgs, ensure_ascii=False, indent=2)
        else:
            lines = [f"# Session {claw.session.session_id}\n"]
            for m in msgs:
                role = m.get("role", "?")
                content = m.get("content", "")
                if isinstance(content, str) and content.strip():
                    lines.append(f"**{role}**: {content}\n")
            out = "\n".join(lines)
        path = f"/tmp/xiaoclaw_export_{claw.session.session_id}.{fmt}"
        Path(path).write_text(out, encoding="utf-8")
        print(f"  Exported to {path}")

    print("─" * 50)
    while True:
        try: user_input = input("\n🧑 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            await _save_session_memory(claw)
            print("\nBye!")
            break
        if not user_input: continue
        cmd = user_input.lower().split()[0] if user_input.startswith("/") else ""
        cmd = ALIASES.get(cmd, cmd)
        if cmd in ("/quit", "/exit"):
            claw.session.save()
            await _save_session_memory(claw)
            print("Bye!")
            break
        if cmd in CMDS: CMDS[cmd](); continue
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
                    print(f"  {sname}: {'enabled' if sk.active else 'disabled'}")
                else:
                    print(f"  Skill not found: {sname}")
            else:
                print("  Usage: /skill on|off <name>")
            continue
        if cmd == "/model":
            for pi in claw.providers.list_providers(): print(f"  {'→' if pi['active'] else ' '} {pi['name']}: {pi['model']}")
            continue
        if cmd == "/sessions":
            for s in claw.session_mgr.list_sessions(): print(f"  {s['session_id']} ({s['size']}B)")
            continue
        if cmd == "/restore":
            parts = user_input.split()
            if len(parts) >= 2:
                sid = parts[1]
                restored = claw.session_mgr.restore(sid)
                if restored:
                    claw.session = restored
                    print(f"  Restored session {sid} ({len(restored.messages)} messages)")
                else:
                    print(f"  Session not found: {sid}")
            else:
                print("  Usage: /restore <session_id>")
            continue
        if cmd == "/export":
            parts = user_input.split()
            fmt = parts[1] if len(parts) >= 2 else "md"
            _export_session("json" if "json" in fmt else "md")
            continue
        if cmd == "/loglevel":
            parts = user_input.split()
            if len(parts) >= 2:
                lvl = parts[1].upper()
                if lvl in ("DEBUG", "INFO", "WARNING", "ERROR"):
                    logging.getLogger().setLevel(getattr(logging, lvl))
                    print(f"  Log level: {lvl}")
                else:
                    print("  Levels: DEBUG INFO WARNING ERROR")
            else:
                print(f"  Current: {logging.getLogger().level}")
            continue
        if cmd == "/reload":
            ok = claw.reload_config(config_path or "config.yaml")
            print(f"  Config {'reloaded' if ok else 'reload failed'}")
            continue
        print(f"\n🐾 xiaoclaw: ", end="", flush=True)
        async for chunk in claw.handle_message_stream(user_input):
            print(chunk, end="", flush=True)
        print()


def _cli_entry():
    """Entry point for `xiaoclaw` console command."""
    asyncio.run(main())
