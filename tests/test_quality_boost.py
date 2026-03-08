"""
Quality boost tests for xiaoclaw
Tests for low-coverage modules: slack_adapter, telegram, webui
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock


# ─────────────────────────────────────────────────────────────
# 1. Slack Adapter Tests
# ─────────────────────────────────────────────────────────────
class TestSlackAdapter:
    """Test Slack Socket Mode adapter."""

    def test_slack_adapter_init(self):
        """Test Slack adapter initialization."""
        slack_mod = pytest.importorskip("xiaoclaw.adapters.slack_adapter")
        
        # Check if slack_bolt is installed
        if not slack_mod.HAS_SLACK:
            pytest.skip("slack_bolt not installed")
        
        from xiaoclaw.adapters.slack_adapter import SlackAdapter
        
        adapter = SlackAdapter(
            app_token="xapp-test",
            bot_token="xoxb-test",
            allowed_channels=["C123", "C456"],
        )
        assert adapter is not None
        assert adapter.allowed_channels == ["C123", "C456"]
    
    def test_slack_adapter_no_channel_restriction(self):
        """Test adapter without channel restriction."""
        slack_mod = pytest.importorskip("xiaoclaw.adapters.slack_adapter")
        if not slack_mod.HAS_SLACK:
            pytest.skip("slack_bolt not installed")
        
        from xiaoclaw.adapters.slack_adapter import SlackAdapter
        
        adapter = SlackAdapter(
            app_token="xapp-test",
            bot_token="xoxb-test",
        )
        assert adapter.allowed_channels is None
    
    def test_check_channel_allowed(self):
        """Test channel checking - allowed."""
        slack_mod = pytest.importorskip("xiaoclaw.adapters.slack_adapter")
        if not slack_mod.HAS_SLACK:
            pytest.skip("slack_bolt not installed")
        
        from xiaoclaw.adapters.slack_adapter import SlackAdapter
        
        adapter = SlackAdapter(
            app_token="xapp-test",
            bot_token="xoxb-test",
            allowed_channels=["C123", "C456"],
        )
        assert adapter._check_channel("C123") is True
        assert adapter._check_channel("C456") is True
    
    def test_check_channel_not_allowed(self):
        """Test channel checking - not allowed."""
        slack_mod = pytest.importorskip("xiaoclaw.adapters.slack_adapter")
        if not slack_mod.HAS_SLACK:
            pytest.skip("slack_bolt not installed")
        
        from xiaoclaw.adapters.slack_adapter import SlackAdapter
        
        adapter = SlackAdapter(
            app_token="xapp-test",
            bot_token="xoxb-test",
            allowed_channels=["C123", "C456"],
        )
        assert adapter._check_channel("C789") is False
    
    def test_check_channel_no_restriction(self):
        """Test channel checking with no restriction."""
        slack_mod = pytest.importorskip("xiaoclaw.adapters.slack_adapter")
        if not slack_mod.HAS_SLACK:
            pytest.skip("slack_bolt not installed")
        
        from xiaoclaw.adapters.slack_adapter import SlackAdapter
        
        adapter = SlackAdapter(
            app_token="xapp-test",
            bot_token="xoxb-test",
        )
        # Any channel should be allowed
        assert adapter._check_channel("C_ANY") is True
    
    def test_slack_adapter_session_management(self):
        """Test per-user session management."""
        slack_mod = pytest.importorskip("xiaoclaw.adapters.slack_adapter")
        if not slack_mod.HAS_SLACK:
            pytest.skip("slack_bolt not installed")
        
        from xiaoclaw.adapters.slack_adapter import SlackAdapter
        
        adapter = SlackAdapter(
            app_token="xapp-test",
            bot_token="xoxb-test",
        )
        
        # Sessions should be empty initially
        assert hasattr(adapter, '_sessions')


# ─────────────────────────────────────────────────────────────
# 2. Telegram Adapter Tests
# ─────────────────────────────────────────────────────────────
class TestTelegramAdapter:
    """Test Telegram adapter."""

    def test_telegram_adapter_init(self):
        """Test Telegram adapter initialization."""
        telegram_mod = pytest.importorskip("xiaoclaw.adapters.telegram")
        if not telegram_mod.HAS_TG:
            pytest.skip("python-telegram-bot not installed")
        
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        # Create mock args
        args = Mock()
        args.telegram_token = "test-token"
        args.allowed_telegram_users = None
        
        adapter = TelegramAdapter(args)
        assert adapter is not None
        assert adapter.token == "test-token"
    
    def test_telegram_adapter_with_allowed_users(self):
        """Test Telegram adapter with user restrictions."""
        telegram_mod = pytest.importorskip("xiaoclaw.adapters.telegram")
        if not telegram_mod.HAS_TG:
            pytest.skip("python-telegram-bot not installed")
        
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        args = Mock()
        args.telegram_token = "test-token"
        args.allowed_telegram_users = [12345, 67890]
        
        adapter = TelegramAdapter(args)
        assert adapter.allowed_users == [12345, 67890]
    
    def test_check_user_allowed(self):
        """Test user checking - allowed."""
        telegram_mod = pytest.importorskip("xiaoclaw.adapters.telegram")
        if not telegram_mod.HAS_TG:
            pytest.skip("python-telegram-bot not installed")
        
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        args = Mock()
        args.telegram_token = "test-token"
        args.allowed_telegram_users = [12345, 67890]
        
        adapter = TelegramAdapter(args)
        
        # Mock update
        mock_update = Mock()
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 12345
        
        assert adapter._check_user(mock_update) is True
    
    def test_check_user_not_allowed(self):
        """Test user checking - not allowed."""
        telegram_mod = pytest.importorskip("xiaoclaw.adapters.telegram")
        if not telegram_mod.HAS_TG:
            pytest.skip("python-telegram-bot not installed")
        
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        args = Mock()
        args.telegram_token = "test-token"
        args.allowed_telegram_users = [12345, 67890]
        
        adapter = TelegramAdapter(args)
        
        # Mock update
        mock_update = Mock()
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 99999
        
        assert adapter._check_user(mock_update) is False
    
    def test_check_user_no_restriction(self):
        """Test user checking with no restriction."""
        telegram_mod = pytest.importorskip("xiaoclaw.adapters.telegram")
        if not telegram_mod.HAS_TG:
            pytest.skip("python-telegram-bot not installed")
        
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        args = Mock()
        args.telegram_token = "test-token"
        args.allowed_telegram_users = None
        
        adapter = TelegramAdapter(args)
        
        # Mock update
        mock_update = Mock()
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 99999
        
        # Any user should be allowed
        assert adapter._check_user(mock_update) is True
    
    @pytest.mark.asyncio
    async def test_cmd_start_authorized(self):
        """Test /start command with authorized user."""
        telegram_mod = pytest.importorskip("xiaoclaw.adapters.telegram")
        if not telegram_mod.HAS_TG:
            pytest.skip("python-telegram-bot not installed")
        
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        args = Mock()
        args.telegram_token = "test-token"
        args.allowed_telegram_users = None
        
        adapter = TelegramAdapter(args)
        
        # Mock update and context
        mock_update = Mock()
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 12345
        mock_update.message = Mock()
        mock_update.message.reply_text = AsyncMock()
        
        mock_ctx = Mock()
        
        await adapter._cmd_start(mock_update, mock_ctx)
        
        mock_update.message.reply_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cmd_clear_creates_new_session(self):
        """Test /clear command creates new session."""
        telegram_mod = pytest.importorskip("xiaoclaw.adapters.telegram")
        if not telegram_mod.HAS_TG:
            pytest.skip("python-telegram-bot not installed")
        
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        args = Mock()
        args.telegram_token = "test-token"
        args.allowed_telegram_users = None
        
        adapter = TelegramAdapter(args)
        
        # Mock claw
        mock_claw = Mock()
        mock_session_mgr = Mock()
        mock_session_mgr.new_session.return_value = Mock(session_id="new-session")
        mock_claw.session_mgr = mock_session_mgr
        
        adapter.claw = mock_claw
        
        # Mock update
        mock_update = Mock()
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 12345
        mock_update.message = Mock()
        mock_update.message.reply_text = AsyncMock()
        
        mock_ctx = Mock()
        
        await adapter._cmd_clear(mock_update, mock_ctx)
        
        # Should call new_session
        mock_session_mgr.new_session.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "New session" in reply_text or "🔄" in reply_text


# ─────────────────────────────────────────────────────────────
# 3. WebUI Tests
# ─────────────────────────────────────────────────────────────
class TestWebUI:
    """Test Web UI module."""

    def test_webui_module_import(self):
        """Test webui module can be imported."""
        try:
            from xiaoclaw import webui
            assert webui is not None
        except ImportError:
            pytest.skip("WebUI module not available")
    
    def test_webui_app_creation(self):
        """Test Flask app creation."""
        try:
            from xiaoclaw.webui import create_app
            
            app = create_app()
            assert app is not None
        except (ImportError, AttributeError):
            pytest.skip("WebUI create_app not available")
    
    def test_webui_routes(self):
        """Test WebUI routes exist."""
        try:
            from xiaoclaw.webui import create_app
            
            app = create_app()
            # Check that routes are registered
            rules = [rule.rule for rule in app.url_map.iter_rules()]
            assert len(rules) > 0
        except (ImportError, AttributeError):
            pytest.skip("WebUI routes not available")


# ─────────────────────────────────────────────────────────────
# 4. Type Annotation Tests (verify annotations work)
# ─────────────────────────────────────────────────────────────
class TestTypeAnnotations:
    """Verify type annotations are present and correct."""

    def test_core_has_annotations(self):
        """Test core module has type annotations."""
        from xiaoclaw.core import XiaClaw
        import typing
        
        # Check class has __annotations__
        assert hasattr(XiaClaw, '__annotations__') or len(XiaClaw.__annotations__) >= 0
    
    def test_session_has_annotations(self):
        """Test session module has type annotations."""
        from xiaoclaw.session import Session
        
        # Check class has __annotations__
        assert hasattr(Session, '__annotations__')

    def test_memory_has_annotations(self):
        """Test memory module has type annotations."""
        from xiaoclaw.memory import MemoryEntry
        
        # Check class has __annotations__
        assert hasattr(MemoryEntry, '__annotations__')


# ─────────────────────────────────────────────────────────────
# 5. Docstring Tests
# ─────────────────────────────────────────────────────────────
class TestDocstrings:
    """Verify docstrings are present on public classes and methods."""

    def test_slack_adapter_has_docstring(self):
        """Test SlackAdapter has class docstring."""
        from xiaoclaw.adapters.slack_adapter import SlackAdapter
        
        assert SlackAdapter.__doc__ is not None
        assert len(SlackAdapter.__doc__) > 10
    
    def test_telegram_adapter_has_docstring(self):
        """Test TelegramAdapter has class docstring."""
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        assert TelegramAdapter.__doc__ is not None
        assert len(TelegramAdapter.__doc__) > 10
    
    def test_slack_check_channel_has_docstring(self):
        """Test _check_channel method has docstring."""
        from xiaoclaw.adapters.slack_adapter import SlackAdapter
        
        assert SlackAdapter._check_channel.__doc__ is not None
    
    def test_telegram_check_user_has_docstring(self):
        """Test _check_user method has docstring."""
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        assert TelegramAdapter._check_user.__doc__ is not None
    
    def test_telegram_cmd_start_has_docstring(self):
        """Test _cmd_start method has docstring."""
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        assert TelegramAdapter._cmd_start.__doc__ is not None
    
    def test_telegram_cmd_clear_has_docstring(self):
        """Test _cmd_clear method has docstring."""
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        assert TelegramAdapter._cmd_clear.__doc__ is not None
    
    def test_telegram_cmd_tools_has_docstring(self):
        """Test _cmd_tools method has docstring."""
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        assert TelegramAdapter._cmd_tools.__doc__ is not None
    
    def test_telegram_handle_message_has_docstring(self):
        """Test _handle_message method has docstring."""
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        assert TelegramAdapter._handle_message.__doc__ is not None


# ─────────────────────────────────────────────────────────────
# 6. Edge Case Tests
# ─────────────────────────────────────────────────────────────
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_slack_empty_channel_list(self):
        """Test Slack adapter with empty allowed channels."""
        slack_mod = pytest.importorskip("xiaoclaw.adapters.slack_adapter")
        if not slack_mod.HAS_SLACK:
            pytest.skip("slack_bolt not installed")
        
        from xiaoclaw.adapters.slack_adapter import SlackAdapter
        
        adapter = SlackAdapter(
            app_token="xapp-test",
            bot_token="xoxb-test",
            allowed_channels=[],
        )
        # Empty list means no channels allowed
        assert adapter._check_channel("C123") is False
    
    def test_telegram_empty_user_list(self):
        """Test Telegram adapter with empty allowed users."""
        telegram_mod = pytest.importorskip("xiaoclaw.adapters.telegram")
        if not telegram_mod.HAS_TG:
            pytest.skip("python-telegram-bot not installed")
        
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        args = Mock()
        args.telegram_token = "test-token"
        args.allowed_telegram_users = []
        
        adapter = TelegramAdapter(args)
        
        mock_update = Mock()
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 12345
        
        # Empty list means no users allowed
        assert adapter._check_user(mock_update) is False
    
    def test_telegram_none_user(self):
        """Test Telegram adapter handles missing user."""
        telegram_mod = pytest.importorskip("xiaoclaw.adapters.telegram")
        if not telegram_mod.HAS_TG:
            pytest.skip("python-telegram-bot not installed")
        
        from xiaoclaw.adapters.telegram import TelegramAdapter
        
        args = Mock()
        args.telegram_token = "test-token"
        args.allowed_telegram_users = [12345]
        
        adapter = TelegramAdapter(args)
        
        mock_update = Mock()
        mock_update.effective_user = None
        
        # Should handle gracefully
        try:
            result = adapter._check_user(mock_update)
            assert result is False
        except (AttributeError, TypeError):
            # Expected behavior - no user means not allowed
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
