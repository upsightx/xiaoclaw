"""xiaoclaw Tool Registry — built-in tools and OpenAI function definitions"""
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

from .web import web_search as _web_search, web_fetch as _web_fetch

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
    def __init__(self, security, memory=None):
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

    def openai_functions(self) -> List[Dict]:
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
