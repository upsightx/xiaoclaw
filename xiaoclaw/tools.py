"""xiaoclaw Tool Registry — built-in tools and OpenAI function definitions"""
import os
import subprocess
import fnmatch
import re
import json
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
    {"name": "clawhub_search", "desc": "Search ClawHub for available skills to install. Use when you need a capability you don't have.", "params": {
        "type": "object", "properties": {"query": {"type": "string", "description": "Search keywords, e.g. 'weather', 'github', 'email'"}},
        "required": ["query"]}},
    {"name": "clawhub_install", "desc": "Install a skill from ClawHub by its slug name. After install, the skill's tools become available.", "params": {
        "type": "object", "properties": {"slug": {"type": "string", "description": "Skill slug from clawhub search results, e.g. 'weather', 'google-weather'"}},
        "required": ["slug"]}},
    {"name": "clawhub_list", "desc": "List all installed ClawHub skills", "params": {
        "type": "object", "properties": {}, "required": []}},
    {"name": "create_skill", "desc": "Create a new custom skill with code. Use when ClawHub doesn't have what you need.", "params": {
        "type": "object", "properties": {
            "name": {"type": "string", "description": "Skill name (lowercase, no spaces, e.g. 'ip-lookup')"},
            "description": {"type": "string", "description": "What the skill does"},
            "tool_name": {"type": "string", "description": "Name of the tool function to expose"},
            "tool_description": {"type": "string", "description": "Description of the tool function"},
            "tool_params": {"type": "string", "description": "JSON string of parameter definitions, e.g. '{\"ip\": {\"type\": \"string\", \"description\": \"IP address\"}}'"},
            "code": {"type": "string", "description": "Python code for skill.py. Must define a function matching tool_name that accepts keyword args and returns a string."}
        },
        "required": ["name", "description", "tool_name", "code"]}},
]


class ToolRegistry:
    def __init__(self, security, memory=None, skills_registry=None):
        self.tools: Dict[str, Dict] = {}
        self.security = security
        self.memory = memory
        self.skills_registry = skills_registry
        self._disabled: set = set()
        self._extra_tool_defs: List[Dict] = []  # for skill tools
        self._skills_dir: Optional[Path] = None
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
            ("clawhub_search", self._clawhub_search, "Search ClawHub"),
            ("clawhub_install", self._clawhub_install, "Install from ClawHub"),
            ("clawhub_list", self._clawhub_list, "List ClawHub skills"),
            ("create_skill", self._create_skill, "Create custom skill"),
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
        try:
            text = p.read_text(encoding="utf-8")
            if len(text) > 2000:
                return text[:2000] + f"\n... [truncated, {len(text)} chars total, use offset/limit for more]"
            return text
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

    # ─── ClawHub Integration ─────────────────────────────

    def _get_skills_dir(self) -> Path:
        """Get the skills directory path."""
        if self._skills_dir:
            return self._skills_dir
        # Default: project root / skills
        return Path(__file__).parent.parent / "skills"

    def set_skills_dir(self, path: Path):
        """Set the skills directory for clawhub operations."""
        self._skills_dir = path

    def _clawhub_search(self, query="", **kw) -> str:
        """Search ClawHub for skills."""
        if not query:
            return "Error: query is required"
        try:
            r = subprocess.run(
                ["clawhub", "search", query],
                capture_output=True, text=True, timeout=30
            )
            output = (r.stdout + r.stderr).strip()
            if not output:
                return f"No skills found for '{query}'"
            # Parse and format results nicely
            lines = output.split("\n")
            results = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith("-"):
                    continue
                results.append(line)
            if not results:
                return f"No skills found for '{query}'"
            formatted = f"Found {len(results)} skills for '{query}':\n"
            for r_line in results[:10]:
                formatted += f"  • {r_line}\n"
            formatted += "\nUse clawhub_install(slug) to install a skill."
            return formatted
        except subprocess.TimeoutExpired:
            return "Error: clawhub search timed out"
        except FileNotFoundError:
            return "Error: clawhub CLI not found. Is it installed?"
        except Exception as e:
            return f"Error searching ClawHub: {e}"

    def _clawhub_install(self, slug="", **kw) -> str:
        """Install a skill from ClawHub."""
        if not slug:
            return "Error: slug is required"
        skills_dir = self._get_skills_dir()
        skills_dir.mkdir(parents=True, exist_ok=True)
        try:
            r = subprocess.run(
                ["clawhub", "install", slug, "--dir", str(skills_dir), "--no-input"],
                capture_output=True, text=True, timeout=60
            )
            output = (r.stdout + r.stderr).strip()
            if r.returncode != 0:
                return f"Install failed: {output}"
            # Reload skills after install
            if self.skills_registry:
                self.skills_registry.reload_skills(skills_dir)
            return f"✅ Installed skill '{slug}' to {skills_dir}/{slug}\n{output}\nSkills reloaded. New tools may now be available."
        except subprocess.TimeoutExpired:
            return "Error: install timed out (60s)"
        except FileNotFoundError:
            return "Error: clawhub CLI not found. Is it installed?"
        except Exception as e:
            return f"Error installing from ClawHub: {e}"

    def _clawhub_list(self, **kw) -> str:
        """List installed ClawHub skills."""
        skills_dir = self._get_skills_dir()
        try:
            r = subprocess.run(
                ["clawhub", "list", "--dir", str(skills_dir)],
                capture_output=True, text=True, timeout=15
            )
            output = (r.stdout + r.stderr).strip()
            if not output or "No installed" in output:
                # Also list local skill directories
                local_skills = []
                if skills_dir.exists():
                    for d in sorted(skills_dir.iterdir()):
                        if d.is_dir() and not d.name.startswith(('_', '.')):
                            skill_md = d / "SKILL.md"
                            desc = ""
                            if skill_md.exists():
                                first_line = skill_md.read_text(encoding="utf-8").split("\n")[0]
                                desc = first_line.replace("#", "").strip()
                            local_skills.append(f"  • {d.name}" + (f" — {desc}" if desc else ""))
                if local_skills:
                    return "Local skills:\n" + "\n".join(local_skills)
                return "No skills installed. Use clawhub_search to find skills."
            return output
        except Exception as e:
            return f"Error listing skills: {e}"

    # ─── Create Skill ────────────────────────────────────

    def _create_skill(self, name="", description="", tool_name="", tool_description="", tool_params="", code="", **kw) -> str:
        """Create a new custom skill in the skills directory."""
        if not name or not code:
            return "Error: name and code are required"
        if not tool_name:
            tool_name = name.replace("-", "_")
        if not tool_description:
            tool_description = description or f"Custom tool: {tool_name}"
        if not description:
            description = f"Custom skill: {name}"

        skills_dir = self._get_skills_dir()
        skill_dir = skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Parse tool_params
        params_block = ""
        if tool_params:
            try:
                params = json.loads(tool_params) if isinstance(tool_params, str) else tool_params
                param_lines = []
                for pname, pdef in params.items():
                    ptype = pdef.get("type", "string") if isinstance(pdef, dict) else "string"
                    pdesc = pdef.get("description", "") if isinstance(pdef, dict) else str(pdef)
                    param_lines.append(f"  - {pname} ({ptype}): {pdesc}")
                params_block = "\n".join(param_lines)
            except Exception:
                params_block = f"  - (see code for parameters)"

        # Create SKILL.md
        skill_md_content = f"""# {name}
{description}

## tools
- {tool_name}: {tool_description}

## parameters
{params_block if params_block else '  - (see code)'}
"""
        (skill_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

        # Create skill.py
        (skill_dir / "skill.py").write_text(code, encoding="utf-8")

        # Reload skills
        if self.skills_registry:
            self.skills_registry.reload_skills(skills_dir)

        return f"✅ Created skill '{name}' at {skill_dir}/\n  - SKILL.md\n  - skill.py\nSkills reloaded. Tool '{tool_name}' should now be available."
