"""xiaoclaw test suite — pytest-compatible tests"""
import asyncio
import json
import tempfile
import shutil
from pathlib import Path

import pytest

# ─── Fixtures ─────────────────────────────────────────

@pytest.fixture
def tmp_workspace():
    """Create a temporary workspace directory."""
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def config():
    from xiaoclaw.core import XiaClawConfig
    return XiaClawConfig(debug=True, security_level="strict", workspace="/tmp/test_xiaoclaw")


@pytest.fixture
def claw(config):
    from xiaoclaw.core import XiaClaw
    return XiaClaw(config)


# ─── Core Tests ───────────────────────────────────────

class TestConfig:
    def test_from_env(self):
        from xiaoclaw.core import XiaClawConfig
        cfg = XiaClawConfig.from_env()
        assert cfg.security_level in ("strict", "relaxed")
        assert cfg.max_context_tokens > 0

    def test_defaults(self):
        from xiaoclaw.core import XiaClawConfig
        cfg = XiaClawConfig()
        assert cfg.debug is False
        assert cfg.security_level == "strict"
        assert cfg.max_context_tokens == 8000


class TestSecurity:
    def test_dangerous_commands(self, claw):
        assert claw.security.is_dangerous("rm -rf /")
        assert claw.security.is_dangerous("dd if=/dev/zero")
        assert not claw.security.is_dangerous("ls -la")
        assert not claw.security.is_dangerous("echo hello")

    def test_audit_log(self, claw):
        claw.security.log_tool_call("exec", {"command": "ls"})
        # Should not raise


class TestRateLimiter:
    def test_basic(self):
        from xiaoclaw.utils import RateLimiter
        rl = RateLimiter(max_calls=3, window_sec=60)
        assert rl.check("user1")
        assert rl.check("user1")
        assert rl.check("user1")
        assert not rl.check("user1")  # 4th call blocked
        assert rl.remaining("user1") == 0

    def test_different_keys(self):
        from xiaoclaw.utils import RateLimiter
        rl = RateLimiter(max_calls=1, window_sec=60)
        assert rl.check("a")
        assert not rl.check("a")
        assert rl.check("b")  # different key


class TestTokenStats:
    def test_record(self):
        from xiaoclaw.utils import TokenStats
        stats = TokenStats()
        stats.requests = 5
        stats.tool_calls = 3
        assert "5" in stats.summary()
        stats.reset()
        assert stats.requests == 0


# ─── Tools Tests ──────────────────────────────────────

class TestTools:
    def test_list_tools(self, claw):
        names = claw.tools.list_names()
        assert "read" in names
        assert "write" in names
        assert "exec" in names

    def test_read_file(self, claw):
        result = claw.tools.call("read", {"file_path": "/etc/hostname"})
        assert "Error" not in result or len(result) > 0

    def test_write_read(self, claw):
        result = claw.tools.call("write", {"file_path": "/tmp/test_xc.txt", "content": "hello"})
        assert "Written" in result
        result = claw.tools.call("read", {"file_path": "/tmp/test_xc.txt"})
        assert "hello" in result

    def test_exec(self, claw):
        result = claw.tools.call("exec", {"command": "echo test123"})
        assert "test123" in result

    def test_exec_blocked(self, claw):
        result = claw.tools.call("exec", {"command": "rm -rf /"})
        assert "Blocked" in result

    def test_unknown_tool(self, claw):
        result = claw.tools.call("nonexistent", {})
        assert "Error" in result

    def test_disable_enable(self, claw):
        claw.tools.disable_tool("exec")
        assert "exec" not in claw.tools.list_names()
        result = claw.tools.call("exec", {"command": "echo hi"})
        assert "disabled" in result
        claw.tools.enable_tool("exec")
        assert "exec" in claw.tools.list_names()


# ─── Session Tests ────────────────────────────────────

class TestSession:
    def test_create_session(self, tmp_workspace):
        from xiaoclaw.session import Session
        s = Session(session_id="test-1", sessions_dir=tmp_workspace / "sessions")
        s.add_message("user", "Hello")
        s.add_message("assistant", "Hi!")
        assert len(s.messages) == 2
        assert s.token_count > 0

    def test_save_load(self, tmp_workspace):
        from xiaoclaw.session import Session
        sd = tmp_workspace / "sessions"
        s = Session(session_id="test-2", sessions_dir=sd)
        s.add_message("user", "Test message")
        s.save()

        s2 = Session(session_id="test-2", sessions_dir=sd)
        assert s2.load()
        assert len(s2.messages) == 1
        assert s2.messages[0]["content"] == "Test message"

    def test_context_window(self, tmp_workspace):
        from xiaoclaw.session import Session
        s = Session(session_id="test-3", sessions_dir=tmp_workspace / "sessions")
        for i in range(20):
            s.add_message("user", f"Message {i} " * 50)
        ctx = s.get_context_window(max_tokens=500)
        assert len(ctx) < 20  # Should be trimmed

    def test_session_manager(self, tmp_workspace):
        from xiaoclaw.session import SessionManager
        mgr = SessionManager(sessions_dir=tmp_workspace / "sessions")
        s1 = mgr.new_session("s1")
        s1.add_message("user", "Hello")
        s1.save()
        s2 = mgr.new_session("s2")
        s2.add_message("user", "World")
        s2.save()
        sessions = mgr.list_sessions()
        assert len(sessions) == 2
        assert mgr.delete("s1")
        assert len(mgr.list_sessions()) == 1


# ─── Memory Tests ─────────────────────────────────────

class TestMemory:
    def test_write_read(self, tmp_workspace):
        from xiaoclaw.memory import MemoryManager
        mem = MemoryManager(workspace=tmp_workspace)
        mem.write_memory("# Test\n- Entry 1\n- Python decision")
        assert "Entry 1" in mem.read_memory()

    def test_search(self, tmp_workspace):
        from xiaoclaw.memory import MemoryManager
        mem = MemoryManager(workspace=tmp_workspace)
        mem.write_memory("# Memory\n- Python is great\n- JavaScript too")
        results = mem.memory_search("Python")
        assert len(results) > 0

    def test_daily(self, tmp_workspace):
        from xiaoclaw.memory import MemoryManager
        mem = MemoryManager(workspace=tmp_workspace)
        mem.append_daily("- Did something")
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        assert "something" in mem.read_daily(today)


# ─── Provider Tests ───────────────────────────────────

class TestProviders:
    def test_manager(self):
        from xiaoclaw.providers import ProviderManager, ProviderConfig
        mgr = ProviderManager()
        mgr.add(ProviderConfig(name="test", api_key="sk-test", base_url="https://test/v1",
                               models=["m1"], default_model="m1"))
        assert mgr.active_name == "test"
        assert mgr.active.current_model == "m1"

    def test_switch(self):
        from xiaoclaw.providers import ProviderManager, ProviderConfig
        mgr = ProviderManager()
        mgr.add(ProviderConfig(name="a", api_key="k1", base_url="u1", models=["m1"]))
        mgr.add(ProviderConfig(name="b", api_key="k2", base_url="u2", models=["m2"]))
        assert mgr.switch("b")
        assert mgr.active_name == "b"
        assert not mgr.switch("nonexistent")


# ─── Skills Tests ─────────────────────────────────────

class TestSkills:
    def test_builtin_skills(self):
        from xiaoclaw.skills import SkillRegistry, register_builtin_skills
        reg = SkillRegistry()
        register_builtin_skills(reg)
        assert "calculator" in reg.list_skills()
        assert "datetime" in reg.list_skills()
        assert "python" in reg.list_skills()

    def test_calc(self):
        from xiaoclaw.skills import SkillRegistry, register_builtin_skills
        reg = SkillRegistry()
        register_builtin_skills(reg)
        calc = reg.get_tool("calc")
        assert calc("2+3") == "5"

    def test_skill_md_parse(self):
        from xiaoclaw.skills import parse_skill_md
        md = "# Test Skill\nDescription\n\n## read_when\nkeyword1 keyword2\n\n## tools\n- tool1\n- tool2"
        meta = parse_skill_md(md)
        assert meta.name == "Test Skill"
        assert "keyword1" in meta.read_when
        assert "tool1" in meta.tools


# ─── i18n Tests ───────────────────────────────────────

class TestI18n:
    def test_translate(self):
        from xiaoclaw.i18n import t
        assert "xiaoclaw" in t("greeting", version="0.3.0")
        assert "xiaoclaw" in t("greeting", lang="en", version="0.3.0")

    def test_fallback(self):
        from xiaoclaw.i18n import t
        result = t("nonexistent_key")
        assert result == "nonexistent_key"


# ─── Webhook Tests ────────────────────────────────────

class TestWebhook:
    def test_register_handler(self):
        from xiaoclaw.webhook import WebhookServer, generic_webhook
        ws = WebhookServer()
        ws.register("test", "/test", generic_webhook)
        assert len(ws.list_handlers()) == 1
        ws.unregister("test")
        assert len(ws.list_handlers()) == 0

    @pytest.mark.asyncio
    async def test_dispatch(self):
        from xiaoclaw.webhook import WebhookServer, generic_webhook
        ws = WebhookServer()
        ws.register("test", "/hook", generic_webhook)
        result = await ws.dispatch("/hook", b'{"key":"value"}', {})
        assert result.get("ok") is True

    @pytest.mark.asyncio
    async def test_dispatch_not_found(self):
        from xiaoclaw.webhook import WebhookServer
        ws = WebhookServer()
        result = await ws.dispatch("/missing", b'{}', {})
        assert "error" in result

    def test_github_webhook(self):
        from xiaoclaw.webhook import github_webhook
        result = github_webhook(
            {"action": "opened", "repository": {"full_name": "test/repo"},
             "issue": {"title": "Bug"}},
            {"x-github-event": "issues"}
        )
        assert "issue" in result.lower()


# ─── Integration Tests ────────────────────────────────

class TestIntegration:
    @pytest.mark.asyncio
    async def test_handle_message_no_llm(self, claw):
        reply = await claw.handle_message("你好")
        assert "xiaoclaw" in reply.lower() or "你好" in reply

    @pytest.mark.asyncio
    async def test_handle_tools_message(self, claw):
        reply = await claw.handle_message("工具列表")
        assert "read" in reply or "工具" in reply or "tools" in reply.lower()

    def test_health_check(self, claw):
        health = claw.health_check()
        assert health["status"] == "ok"
        assert "version" in health

    def test_version(self):
        from xiaoclaw.core import VERSION
        assert VERSION.startswith("0.3")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
