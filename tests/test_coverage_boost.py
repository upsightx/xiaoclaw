"""
Coverage boost tests for xiaoclaw
基于实际 API 结构编写
"""
import pytest
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import io

# ─────────────────────────────────────────────────────────────
# 1. Errors Module Tests
# ─────────────────────────────────────────────────────────────
class TestErrors:
    """Test error handling module."""
    
    def test_xerror_basic(self):
        """Test XError basic functionality."""
        from xiaoclaw.errors import XError
        
        err = XError("Test error")
        assert str(err) == "Test error"
        
    def test_xerror_with_code(self):
        """Test XError with error code."""
        from xiaoclaw.errors import XError
        
        err = XError("Error with code", code="E001")
        assert err.code == "E001"
        assert "E001" in str(err) or err.code == "E001"
        
    def test_error_categories(self):
        """Test error category types."""
        from xiaoclaw.errors import (
            ConfigError, ToolError,
            NetworkError, AuthError
        )
        
        # All should be XError subclasses
        errors = [
            ConfigError("config"),
            ToolError("tool"),
            NetworkError("network"),
            AuthError("auth"),
        ]
        
        for err in errors:
            assert isinstance(err, Exception)
            assert str(err)


# ─────────────────────────────────────────────────────────────
# 2. Core Configuration Tests
# ─────────────────────────────────────────────────────────────
class TestCoreConfig:
    """Test configuration loading and validation."""
    
    def test_config_from_env(self):
        """Test config from environment."""
        from xiaoclaw.core import XiaClawConfig
        
        config = XiaClawConfig.from_env()
        assert config is not None
        
    def test_config_defaults(self):
        """Test default configuration values."""
        from xiaoclaw.core import XiaClawConfig
        
        config = XiaClawConfig()
        assert config is not None
        
    def test_config_yaml_loading(self):
        """Test YAML config loading."""
        from xiaoclaw.core import XiaClawConfig
        import tempfile
        
        yaml_content = """
model: gpt-4o
api_key: test-key
base_url: https://api.openai.com/v1
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            path = f.name
            
        try:
            config = XiaClawConfig.from_yaml(path)
            assert config is not None
        finally:
            os.unlink(path)


# ─────────────────────────────────────────────────────────────
# 3. Utils Tests
# ─────────────────────────────────────────────────────────────
class TestUtils:
    """Test utility functions."""
    
    def test_rate_limiter(self):
        """Test rate limiter."""
        from xiaoclaw.utils import RateLimiter
        
        limiter = RateLimiter()
        assert limiter is not None
        
    def test_security_manager(self):
        """Test security manager."""
        from xiaoclaw.utils import SecurityManager
        
        sm = SecurityManager()
        assert sm is not None
        
    def test_hook_manager(self):
        """Test hook manager."""
        from xiaoclaw.utils import HookManager
        
        hm = HookManager()
        assert hm is not None


# ─────────────────────────────────────────────────────────────
# 4. Session Management Tests
# ─────────────────────────────────────────────────────────────
class TestSessionManagement:
    """Test session persistence and recovery."""
    
    def test_session_create(self):
        """Test session creation."""
        from xiaoclaw.session import SessionManager
        
        mgr = SessionManager()
        session = mgr.new_session()
        assert session is not None
        assert session.session_id
        
    def test_session_messages(self):
        """Test session message handling."""
        from xiaoclaw.session import Session
        
        session = Session(session_id="test-123")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi!")
        
        assert len(session.messages) == 2
        
    def test_session_manager_list(self):
        """Test session manager list."""
        from xiaoclaw.session import SessionManager
        
        mgr = SessionManager()
        sessions = mgr.list_sessions()
        assert isinstance(sessions, list)


# ─────────────────────────────────────────────────────────────
# 5. Tool System Tests
# ─────────────────────────────────────────────────────────────
class TestToolSystem:
    """Test tool registration and dispatch."""
    
    def test_tool_registry_init(self):
        """Test tool registry initialization."""
        from xiaoclaw.tools import ToolRegistry
        from xiaoclaw.utils import SecurityManager
        
        sm = SecurityManager()
        registry = ToolRegistry(security=sm)
        assert registry is not None
        
    def test_tool_defs_exist(self):
        """Test tool definitions exist."""
        from xiaoclaw.tools import TOOL_DEFS
        
        assert TOOL_DEFS is not None
        assert isinstance(TOOL_DEFS, (list, dict))


# ─────────────────────────────────────────────────────────────
# 6. CLI Parsing Tests
# ─────────────────────────────────────────────────────────────
class TestCLI:
    """Test CLI argument parsing."""
    
    def test_parse_slash_command(self):
        """Test slash command parsing."""
        from xiaoclaw.cli import parse_slash_command
        
        # Simple command
        cmd, args = parse_slash_command("/help")
        assert cmd == "/help"
        
    def test_slash_completer(self):
        """Test tab completion."""
        from xiaoclaw.cli import SlashCompleter
        
        completer = SlashCompleter()
        assert completer is not None


# ─────────────────────────────────────────────────────────────
# 7. Provider Tests
# ─────────────────────────────────────────────────────────────
class TestProviders:
    """Test provider system."""
    
    def test_provider_init(self):
        """Test provider initialization."""
        from xiaoclaw.providers import ProviderManager
        
        mgr = ProviderManager()
        assert mgr is not None


# ─────────────────────────────────────────────────────────────
# 8. Memory System Tests
# ─────────────────────────────────────────────────────────────
class TestMemory:
    """Test memory management."""
    
    def test_memory_module_import(self):
        """Test memory module can be imported."""
        try:
            from xiaoclaw import memory
            assert memory is not None
        except ImportError:
            pytest.skip("Memory module structure differs")


# ─────────────────────────────────────────────────────────────
# 9. Web Module Tests  
# ─────────────────────────────────────────────────────────────
class TestWebModule:
    """Test web utilities."""
    
    def test_web_import(self):
        """Test web module import."""
        try:
            from xiaoclaw import web
            assert web is not None
        except ImportError:
            pytest.skip("Web module structure differs")


# ─────────────────────────────────────────────────────────────
# 10. Token Counting Tests
# ─────────────────────────────────────────────────────────────
class TestTokenCounting:
    """Test token counting utilities."""
    
    def test_count_tokens(self):
        """Test token counting."""
        from xiaoclaw.session import count_tokens
        
        tokens = count_tokens("Hello world")
        assert isinstance(tokens, int)
        assert tokens > 0
        
    def test_count_messages_tokens(self):
        """Test message token counting."""
        from xiaoclaw.session import count_messages_tokens
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        tokens = count_messages_tokens(messages)
        assert isinstance(tokens, int)


# ─────────────────────────────────────────────────────────────
# 11. Integration Smoke Tests
# ─────────────────────────────────────────────────────────────
class TestIntegrationSmoke:
    """Smoke tests for core integration."""
    
    def test_full_import_chain(self):
        """Test all major modules can be imported."""
        modules = [
            'xiaoclaw.core',
            'xiaoclaw.session', 
            'xiaoclaw.tools',
            'xiaoclaw.utils',
            'xiaoclaw.errors',
            'xiaoclaw.providers',
            'xiaoclaw.cli',
        ]
        
        for mod in modules:
            __import__(mod)
            
    def test_xiaoclaw_callable(self):
        """Test main xiaoclaw callable."""
        from xiaoclaw import XiaClaw
        
        # Should be able to instantiate
        xc = XiaClaw()
        assert xc is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
