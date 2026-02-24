"""xiaoclaw Memory System - Compatible with OpenClaw memory format"""
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger("xiaoclaw.Memory")

DEFAULT_WORKSPACE = Path(".")


class MemoryManager:
    """Manages MEMORY.md + memory/YYYY-MM-DD.md files."""

    def __init__(self, workspace: Path = DEFAULT_WORKSPACE):
        self.workspace = workspace
        self.memory_file = workspace / "MEMORY.md"
        self.memory_dir = workspace / "memory"

    def _ensure_dir(self):
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    # ─── memory_search ────────────────────────────────

    def memory_search(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search MEMORY.md + memory/*.md for matching lines (keyword-based)."""
        results = []
        keywords = [w.lower() for w in query.split() if len(w) > 1]
        if not keywords:
            return results

        # Search MEMORY.md
        if self.memory_file.exists():
            results.extend(self._search_file(self.memory_file, keywords, max_results))

        # Search memory/*.md (recent first)
        if self.memory_dir.exists():
            md_files = sorted(self.memory_dir.glob("*.md"), reverse=True)
            for f in md_files[:30]:  # limit to recent 30 files
                if len(results) >= max_results:
                    break
                results.extend(self._search_file(f, keywords, max_results - len(results)))

        return results[:max_results]

    def _search_file(self, filepath: Path, keywords: List[str], limit: int) -> List[Dict]:
        results = []
        try:
            lines = filepath.read_text(encoding="utf-8").split("\n")
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                lower = line.lower()
                score = sum(1 for kw in keywords if kw in lower)
                if score > 0:
                    results.append({
                        "file": str(filepath.relative_to(self.workspace)),
                        "line": i + 1,
                        "content": line.strip(),
                        "score": score,
                    })
            results.sort(key=lambda x: x["score"], reverse=True)
        except Exception as e:
            logger.error(f"Error searching {filepath}: {e}")
        return results[:limit]

    # ─── memory_get ───────────────────────────────────

    def memory_get(self, file_path: str, start_line: int = 1, end_line: int = 0) -> str:
        """Read specific lines from a memory file."""
        fp = self.workspace / file_path
        if not fp.exists():
            return f"Error: file not found: {file_path}"
        try:
            lines = fp.read_text(encoding="utf-8").split("\n")
            if end_line <= 0:
                end_line = len(lines)
            selected = lines[max(0, start_line - 1):end_line]
            return "\n".join(selected)
        except Exception as e:
            return f"Error: {e}"

    # ─── Read helpers ─────────────────────────────────

    def read_memory(self) -> str:
        """Read MEMORY.md content."""
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def read_daily(self, date: Optional[str] = None) -> str:
        """Read memory/YYYY-MM-DD.md for given date (default: today)."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        fp = self.memory_dir / f"{date}.md"
        if fp.exists():
            return fp.read_text(encoding="utf-8")
        return ""

    def read_recent_daily(self, days: int = 2) -> Dict[str, str]:
        """Read recent daily memory files."""
        result = {}
        today = datetime.now()
        for i in range(days):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            content = self.read_daily(d)
            if content:
                result[d] = content
        return result

    # ─── Write helpers ────────────────────────────────

    def write_memory(self, content: str):
        """Overwrite MEMORY.md."""
        self.memory_file.write_text(content, encoding="utf-8")
        logger.info("MEMORY.md updated")

    def append_memory(self, text: str):
        """Append to MEMORY.md."""
        existing = self.read_memory()
        self.memory_file.write_text(
            existing.rstrip() + "\n\n" + text.strip() + "\n", encoding="utf-8"
        )

    def append_daily(self, text: str, date: Optional[str] = None):
        """Append to today's daily memory file."""
        self._ensure_dir()
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        fp = self.memory_dir / f"{date}.md"
        existing = fp.read_text(encoding="utf-8") if fp.exists() else f"# {date}\n"
        fp.write_text(existing.rstrip() + "\n\n" + text.strip() + "\n", encoding="utf-8")
        logger.info(f"Daily memory updated: {date}")

    # ─── Flush (pre-compaction) ───────────────────────

    def flush_important(self, messages: List[Dict], summary: str = ""):
        """Save important info from messages before compaction."""
        self._ensure_dir()
        today = datetime.now().strftime("%Y-%m-%d")
        entries = []
        if summary:
            entries.append(f"## Compaction Summary\n{summary}")
        # Extract user decisions, key facts
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            # Heuristic: save lines with "remember", "important", "决定", "记住"
            for line in content.split("\n"):
                lower = line.lower()
                if any(kw in lower for kw in ["remember", "important", "决定", "记住", "注意", "todo"]):
                    entries.append(f"- {line.strip()}")
        if entries:
            self.append_daily("\n".join(entries), date=today)

    # ─── Workspace bootstrap files ────────────────────

    def read_bootstrap_files(self) -> Dict[str, str]:
        """Read AGENTS.md, SOUL.md, USER.md, IDENTITY.md for system prompt."""
        files = {}
        for name in ["AGENTS.md", "SOUL.md", "USER.md", "IDENTITY.md"]:
            fp = self.workspace / name
            if fp.exists():
                try:
                    files[name] = fp.read_text(encoding="utf-8")
                except Exception:
                    pass
        return files


def test_memory():
    """Quick self-test."""
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp())
    try:
        mem = MemoryManager(workspace=tmp)

        # Write and read MEMORY.md
        mem.write_memory("# Long-term Memory\n- Test entry 1\n- Important decision about Python")
        assert "Test entry" in mem.read_memory()

        # Append
        mem.append_memory("- New entry added")
        assert "New entry" in mem.read_memory()

        # Daily
        mem.append_daily("- Did something today")
        today = datetime.now().strftime("%Y-%m-%d")
        assert "something today" in mem.read_daily(today)

        # Search
        results = mem.memory_search("Python decision")
        assert len(results) > 0
        assert results[0]["score"] > 0

        # memory_get
        content = mem.memory_get("MEMORY.md", 1, 3)
        assert "Memory" in content

        # Flush
        msgs = [{"role": "user", "content": "Please remember this: use pytest for testing"}]
        mem.flush_important(msgs)
        daily = mem.read_daily(today)
        assert "remember" in daily.lower() or "pytest" in daily.lower()

        # Bootstrap files
        (tmp / "SOUL.md").write_text("I am xiaoclaw")
        files = mem.read_bootstrap_files()
        assert "SOUL.md" in files

        print("  ✓ memory.py tests passed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_memory()
