"""xiaoclaw Tool Registry — built-in tools and OpenAI function definitions"""
import os
import subprocess
import fnmatch
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

from .web import web_search as _web_search, web_fetch as _web_fetch

TOOL_DEFS = [
    {"name": "read", "desc": "Read a file's contents", "params": {
        "type": "object", "properties": {"file_path": {"type": "string", "description": "Path to file"}},
        "required": ["file_path"]}},
    {"name": "write", "desc": "Write content to a file (creates parent dirs)", "params": {
        "type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["file_path", "content"]}},
    {"name": "edit", "desc": "Edit a file by replacing exact text", "params": {
        "type": "object", "properties": {"file_path": {"type": "string"}, "old_string": {"type": "string", "description": "Exact text to find"}, "new_string": {"type": "string", "description": "Replacement text"}},
        "required": ["file_path", "old_string", "new_string"]}},
    {"name": "exec", "desc": "Run a shell command and return output", "params": {
        "type": "object", "properties": {"command": {"type": "string", "description": "Shell command to execute"}},
        "required": ["command"]}},
    {"name": "web_search", "desc": "Search the web using DuckDuckGo", "params": {
        "type": "object", "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"]}},
    {"name": "web_fetch", "desc": "Fetch and extract readable content from a URL", "params": {
        "type": "object", "properties": {"url": {"type": "string", "description": "URL to fetch"}},
        "required": ["url"]}},
    {"name": "memory_search", "desc": "Search through memory files (MEMORY.md and daily notes) for relevant information", "params": {
        "type": "object", "properties": {"query": {"type": "string", "description": "Search keywords"}},
        "required": ["query"]}},
    {"name": "memory_get", "desc": "Read specific lines from a memory file", "params": {
        "type": "object", "properties": {"file_path": {"type": "string", "description": "Relative path like MEMORY.md or memory/2024-01-01.md"}, "start_line": {"type": "integer", "description": "Start line (1-indexed)"}, "end_line": {"type": "integer", "description": "End line (0=all)"}},
        "required": ["file_path"]}},
    {"name": "memory_save", "desc": "Save important information to daily memory or MEMORY.md", "params": {
        "type": "object", "properties": {"content": {"type": "string", "description": "Content to save"}, "daily": {"type": "boolean", "description": "If true, save to today's daily file; if false, append to MEMORY.md"}},
        "required": ["content"]}},
    {"name": "list_dir", "desc": "List directory contents with file sizes", "params": {
        "type": "object", "properties": {"path": {"type": "string", "description": "Directory path (default: current dir)"}},
        "required": []}},
    {"name": "find_files", "desc": "Find files matching a glob pattern", "params": {
        "type": "object", "properties": {"pattern": {"type": "string", "description": "Glob pattern like *.py or **/*.md"}, "path": {"type": "string", "description": "Root directory to search (default: .)"}},
        "required": ["pattern"]}},
    {"name": "grep", "desc": "Search file contents for a pattern (regex supported)", "params": {
        "type": "object", "properties": {"pattern": {"type": "string", "description": "Search pattern (regex)"}, "path": {"type": "string", "description": "File or directory to search"}, "max_results": {"type": "integer", "description": "Max results (default: 20)"}},
        "required": ["pattern"]}},
]


class ToolRegistry:
    def __init__(self, security, memory=None):
        self.tools: Dict[str, Dict] = {}
        self.security = security
        self.memory = memory
        self._disabled: set = set()
        self._extra_tool_defs: List[Dict] = []  # for skill tools
        for n, f, d in [
            ("read", self._read, "Read file"),
            ("write", self._write, "Write file"),
            ("edit", self._edit, "Edit file"),
            ("exec", self._exec, "Run command"),
            ("web_search", lambda **kw: _web_search(**kw), "Search web"),
            ("web_fetch", lambda **kw: _web_fetch(**kw), "Fetch URL"),
            ("memory_search", self._memory_search, "Search memory"),
            ("memory_get", self._memory_get, "Get memory"),
            ("memory_save", self._memory_save, "Save to memory"),
            ("list_dir", self._list_dir, "List directory"),
            ("find_files", self._find_files, "Find files"),
            ("grep", self._grep, "Search file contents"),
        ]:
            self.tools[n] = {"func": f, "description": d}

    def get(self, name: str): return self.tools.get(name)
    def list_names(self) -> List[str]: return [n for n in self.tools if n not in self._disabled]

    def disable_tool(self, name: str):
        self._disabled.add(name)

    def enable_tool(self, name: str):
        self._disabled.discard(name)

    def register_tool(self, name: str, func: Callable, description: str, params: Dict):
        """Register an additional tool (e.g. from skills)."""
        self.tools[name] = {"func": func, "description": description}
        self._extra_tool_defs.append({
            "name": name, "desc": description, "params": params
        })

    def call(self, name: str, args: Dict) -> str:
        if name in self._disabled:
            return f"Error: tool '{name}' is disabled"
        tool = self.tools.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'. Available: {', '.join(self.list_names())}"
        try:
            return str(tool["func"](**args))
        except TypeError as e:
            return f"Error calling {name}: bad arguments — {e}"
        except PermissionError as e:
            return f"Error calling {name}: permission denied — {e}"
        except FileNotFoundError as e:
            return f"Error calling {name}: file not found — {e}"
        except Exception as e:
            return f"Error calling {name}: {type(e).__name__}: {e}"

    def get_all_tool_defs(self) -> List[Dict]:
        """Get all tool definitions (built-in + extra from skills)."""
        return TOOL_DEFS + self._extra_tool_defs

    def openai_functions(self) -> List[Dict]:
        all_defs = self.get_all_tool_defs()
        return [{"type": "function", "function": {
            "name": t["name"], "description": t["desc"], "parameters": t["params"],
        }} for t in all_defs if t["name"] not in self._disabled]

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
        if old_string not in text: return "Error: old_string not found in file"
        p.write_text(text.replace(old_string, new_string, 1), encoding="utf-8"); return f"Edited: {p}"

    def _exec(self, command="", **kw) -> str:
        if self.security.is_dangerous(command): return f"Blocked: dangerous command"
        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return ((r.stdout + r.stderr).strip() or "(no output)")[:5000]
        except subprocess.TimeoutExpired: return "Error: command timed out (30s)"
        except Exception as e: return f"Error: {e}"

    def _memory_search(self, query="", **kw) -> str:
        if not self.memory: return "Error: memory not configured"
        results = self.memory.memory_search(query)
        if not results: return "No results found"
        return "\n".join(f"[{r['file']}:{r['line']}] {r['content']}" for r in results[:10])

    def _memory_get(self, file_path="", start_line=1, end_line=0, **kw) -> str:
        if not self.memory: return "Error: memory not configured"
        return self.memory.memory_get(file_path, int(start_line), int(end_line))

    def _memory_save(self, content="", daily=True, **kw) -> str:
        if not self.memory: return "Error: memory not configured"
        try:
            if daily:
                self.memory.append_daily(content)
                from datetime import datetime
                date = datetime.now().strftime("%Y-%m-%d")
                return f"Saved to memory/{date}.md"
            else:
                self.memory.append_memory(content)
                return "Saved to MEMORY.md"
        except Exception as e:
            return f"Error saving memory: {e}"

    def _list_dir(self, path=".", **kw) -> str:
        p = Path(path).expanduser()
        if not p.exists(): return f"Error: not found: {p}"
        if not p.is_dir(): return f"Error: not a directory: {p}"
        entries = []
        try:
            for item in sorted(p.iterdir()):
                if item.name.startswith('.'):
                    continue
                if item.is_dir():
                    entries.append(f"📁 {item.name}/")
                else:
                    size = item.stat().st_size
                    if size < 1024:
                        sz = f"{size}B"
                    elif size < 1024 * 1024:
                        sz = f"{size // 1024}KB"
                    else:
                        sz = f"{size // (1024*1024)}MB"
                    entries.append(f"📄 {item.name} ({sz})")
            return "\n".join(entries) if entries else "(empty directory)"
        except Exception as e:
            return f"Error: {e}"

    def _find_files(self, pattern="", path=".", **kw) -> str:
        p = Path(path).expanduser()
        if not p.exists(): return f"Error: not found: {p}"
        results = []
        try:
            if "**" in pattern:
                matches = list(p.glob(pattern))
            else:
                matches = list(p.rglob(pattern))
            for m in matches[:50]:
                if '.git' in str(m) or '__pycache__' in str(m) or 'venv' in str(m) or 'node_modules' in str(m):
                    continue
                try:
                    rel = m.relative_to(p)
                except ValueError:
                    rel = m
                results.append(str(rel))
            return "\n".join(results) if results else f"No files matching '{pattern}'"
        except Exception as e:
            return f"Error: {e}"

    def _grep(self, pattern="", path=".", max_results=20, **kw) -> str:
        p = Path(path).expanduser()
        if not p.exists(): return f"Error: not found: {p}"
        results = []
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"Error: invalid regex: {e}"

        def _search_file(fp: Path):
            try:
                lines = fp.read_text(encoding="utf-8", errors="ignore").split("\n")
                for i, line in enumerate(lines):
                    if regex.search(line):
                        try:
                            rel = fp.relative_to(Path(path).expanduser())
                        except ValueError:
                            rel = fp
                        results.append(f"{rel}:{i+1}: {line.strip()[:120]}")
                        if len(results) >= int(max_results):
                            return
            except Exception:
                pass

        if p.is_file():
            _search_file(p)
        else:
            for fp in p.rglob("*"):
                if len(results) >= int(max_results):
                    break
                if fp.is_file() and fp.suffix in ('.py', '.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.sh', '.js', '.ts', '.html', '.css', '.xml', '.csv'):
                    if '.git' not in str(fp) and '__pycache__' not in str(fp) and 'venv' not in str(fp) and 'node_modules' not in str(fp):
                        _search_file(fp)

        return "\n".join(results) if results else f"No matches for '{pattern}'"
