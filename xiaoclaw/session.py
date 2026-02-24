"""xiaoclaw Session Management - JSONL persistence compatible with OpenClaw"""
import json
import time
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

logger = logging.getLogger("xiaoclaw.Session")

DEFAULT_SESSIONS_DIR = Path(".xiaoclaw/sessions")


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens using tiktoken, fallback to char estimate."""
    if HAS_TIKTOKEN:
        try:
            enc = tiktoken.encoding_for_model(model)
            return len(enc.encode(text))
        except Exception:
            pass
    return len(text) // 3  # rough estimate


def count_messages_tokens(messages: List[Dict], model: str = "gpt-4") -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += count_tokens(content, model) + 4  # overhead per message
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += count_tokens(part.get("text", ""), model) + 4
    return total


class Session:
    """A single conversation session with JSONL persistence."""

    def __init__(self, session_id: str = "", sessions_dir: Path = DEFAULT_SESSIONS_DIR):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.sessions_dir = sessions_dir
        self.messages: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self._file = self.sessions_dir / f"{self.session_id}.jsonl"

    @property
    def token_count(self) -> int:
        return count_messages_tokens(self.messages)

    def add_message(self, role: str, content: str, **extra) -> Dict:
        msg = {"role": role, "content": content, "ts": time.time()}
        # Preserve tool_calls, tool_call_id, name for function calling
        for k in ("tool_calls", "tool_call_id", "name"):
            if k in extra:
                msg[k] = extra[k]
        self.messages.append(msg)
        self.metadata["updated_at"] = time.time()
        self._append_line(msg)
        return msg

    def _append_line(self, data: Dict):
        """Append a single JSONL line to the session file."""
        self._file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def save(self):
        """Full save (rewrite entire file)."""
        self._file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file, "w", encoding="utf-8") as f:
            # First line is metadata
            f.write(json.dumps({"_meta": True, **self.metadata}, ensure_ascii=False) + "\n")
            for msg in self.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def load(self) -> bool:
        """Load session from JSONL file."""
        if not self._file.exists():
            return False
        self.messages.clear()
        try:
            for line in self._file.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("_meta"):
                    self.metadata.update(data)
                else:
                    self.messages.append(data)
            logger.info(f"Session '{self.session_id}' loaded: {len(self.messages)} messages")
            return True
        except Exception as e:
            logger.error(f"Failed to load session '{self.session_id}': {e}")
            return False

    def clear(self):
        self.messages.clear()
        if self._file.exists():
            self._file.unlink()

    def get_context_window(self, max_tokens: int = 8000) -> List[Dict]:
        """Get recent messages fitting within token budget, preserving tool call structure."""
        result = []
        tokens = 0
        for msg in reversed(self.messages):
            content = msg.get("content", "")
            mt = count_tokens(content) + 4 if isinstance(content, str) else 100
            if tokens + mt > max_tokens and result:
                break
            # Build API-compatible message
            m = {"role": msg["role"], "content": content}
            if "tool_calls" in msg:
                m["tool_calls"] = msg["tool_calls"]
            if "tool_call_id" in msg:
                m["tool_call_id"] = msg["tool_call_id"]
            if "name" in msg and msg["role"] == "tool":
                m["name"] = msg["name"]
            result.insert(0, m)
            tokens += mt
        return result


class SessionManager:
    """Manages multiple sessions with list/restore/delete."""

    def __init__(self, sessions_dir: Path = DEFAULT_SESSIONS_DIR):
        self.sessions_dir = sessions_dir
        self.current: Optional[Session] = None

    def new_session(self, session_id: str = "") -> Session:
        s = Session(session_id=session_id, sessions_dir=self.sessions_dir)
        self.current = s
        logger.info(f"New session: {s.session_id}")
        return s

    def restore(self, session_id: str) -> Optional[Session]:
        s = Session(session_id=session_id, sessions_dir=self.sessions_dir)
        if s.load():
            self.current = s
            return s
        return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        result = []
        if not self.sessions_dir.exists():
            return result
        for f in sorted(self.sessions_dir.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True):
            sid = f.stem
            try:
                first_line = f.read_text(encoding="utf-8").split("\n")[0]
                meta = json.loads(first_line) if first_line else {}
            except Exception:
                meta = {}
            result.append({
                "session_id": sid,
                "file": str(f),
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
                "meta": meta if meta.get("_meta") else {},
            })
        return result

    def delete(self, session_id: str) -> bool:
        f = self.sessions_dir / f"{session_id}.jsonl"
        if f.exists():
            f.unlink()
            if self.current and self.current.session_id == session_id:
                self.current = None
            logger.info(f"Deleted session: {session_id}")
            return True
        return False


def test_session():
    """Quick self-test."""
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp()) / "sessions"
    try:
        # Test Session
        s = Session(session_id="test-001", sessions_dir=tmp)
        s.add_message("user", "Hello")
        s.add_message("assistant", "Hi there!")
        assert len(s.messages) == 2
        assert s.token_count > 0

        # Test save/load
        s.save()
        s2 = Session(session_id="test-001", sessions_dir=tmp)
        assert s2.load()
        assert len(s2.messages) == 2

        # Test context window
        ctx = s2.get_context_window(max_tokens=100)
        assert len(ctx) > 0

        # Test SessionManager
        mgr = SessionManager(sessions_dir=tmp)
        mgr.new_session("test-002")
        mgr.current.add_message("user", "Test")
        mgr.current.save()
        sessions = mgr.list_sessions()
        assert len(sessions) >= 1

        # Test restore
        restored = mgr.restore("test-001")
        assert restored is not None
        assert len(restored.messages) == 2

        # Test delete
        assert mgr.delete("test-002")
        assert not (tmp / "test-002.jsonl").exists()

        print("  ✓ session.py tests passed")
    finally:
        shutil.rmtree(tmp.parent if tmp.name == "sessions" else tmp, ignore_errors=True)


if __name__ == "__main__":
    test_session()
