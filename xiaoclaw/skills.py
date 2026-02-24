"""xiaoclaw Skill System - Compatible with OpenClaw ClawHub format"""
import re
import logging
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

logger = logging.getLogger("xiaoclaw.Skills")


@dataclass
class SkillMeta:
    """Metadata parsed from SKILL.md."""
    name: str = ""
    description: str = ""
    read_when: str = ""  # condition to auto-activate
    tools: List[str] = field(default_factory=list)
    raw_content: str = ""


@dataclass
class Skill:
    name: str
    description: str
    tools: Dict[str, Callable] = field(default_factory=dict)
    meta: Optional[SkillMeta] = None
    active: bool = False

    def __repr__(self):
        status = "active" if self.active else "inactive"
        return f"<Skill: {self.name} [{status}] tools={list(self.tools.keys())}>"


def parse_skill_md(content: str) -> SkillMeta:
    """Parse SKILL.md into SkillMeta. Compatible with OpenClaw ClawHub format.

    Expected format:
    ```
    # Skill Name
    Description text...

    ## read_when
    condition text

    ## tools
    - tool_name: description
    ```
    """
    meta = SkillMeta(raw_content=content)

    lines = content.strip().split("\n")
    if not lines:
        return meta

    # Parse name from first heading
    for line in lines:
        if line.startswith("# "):
            meta.name = line[2:].strip()
            break

    # Parse sections
    current_section = "description"
    sections: Dict[str, List[str]] = {"description": []}

    for line in lines:
        heading = re.match(r'^##\s+(.+)', line)
        if heading:
            current_section = heading.group(1).strip().lower().replace(" ", "_")
            sections.setdefault(current_section, [])
            continue
        if line.startswith("# "):
            continue
        sections.setdefault(current_section, []).append(line)

    # Extract fields
    meta.description = "\n".join(sections.get("description", [])).strip()

    if "read_when" in sections:
        meta.read_when = "\n".join(sections["read_when"]).strip()

    if "tools" in sections:
        for line in sections["tools"]:
            m = re.match(r'^\s*[-*]\s+(\w+)', line)
            if m:
                meta.tools.append(m.group(1))

    return meta


def should_activate(meta: SkillMeta, user_message: str) -> bool:
    """Check if a skill should be activated based on user message."""
    if not meta.read_when:
        return False

    msg_lower = user_message.lower()
    conditions = meta.read_when.lower()

    # Simple keyword matching from read_when
    keywords = re.findall(r'\w+', conditions)
    if not keywords:
        return False

    # Activate if any keyword matches
    match_count = sum(1 for kw in keywords if kw in msg_lower and len(kw) > 2)
    return match_count > 0


class SkillRegistry:
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.tools: Dict[str, Callable] = {}
        self._skills_dir: Optional[Path] = None

    def register(self, skill: Skill):
        self.skills[skill.name] = skill
        for name, func in skill.tools.items():
            self.tools[name] = func
        logger.info(f"Registered skill: {skill.name} ({len(skill.tools)} tools)")

    def reload_skills(self, skills_dir: Optional[Path] = None):
        """Reload all skills from directory. Used after installing new skills."""
        d = skills_dir or self._skills_dir
        if d and d.exists():
            self.load_from_dir(d)
            return True
        return False

    def get_skill(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    def list_skills(self) -> List[str]:
        return list(self.skills.keys())

    def get_tool(self, name: str) -> Optional[Callable]:
        return self.tools.get(name)

    def list_tools(self) -> List[str]:
        return list(self.tools.keys())

    def activate_for_message(self, message: str) -> List[Skill]:
        """Auto-activate skills based on user message."""
        activated = []
        for skill in self.skills.values():
            if skill.meta and should_activate(skill.meta, message):
                skill.active = True
                activated.append(skill)
                logger.info(f"Auto-activated skill: {skill.name}")
        return activated

    def get_active_skills(self) -> List[Skill]:
        return [s for s in self.skills.values() if s.active]

    def deactivate_all(self):
        for s in self.skills.values():
            s.active = False

    def load_from_dir(self, skills_dir: Path):
        """Load skills from directory. Supports both flat and nested layouts."""
        self._skills_dir = skills_dir
        if not skills_dir.exists():
            logger.warning(f"Skills directory not found: {skills_dir}")
            return

        # Nested: skills/name/SKILL.md + skill.py
        for skill_md in skills_dir.rglob("SKILL.md"):
            skill_dir = skill_md.parent
            meta = parse_skill_md(skill_md.read_text(encoding="utf-8"))
            if not meta.name:
                meta.name = skill_dir.name

            skill = Skill(name=meta.name, description=meta.description, meta=meta)

            # Load skill.py if exists
            skill_py = skill_dir / "skill.py"
            if skill_py.exists():
                self._load_skill_module(skill, skill_py)

            self.register(skill)

        # Flat: skills/*.py (without SKILL.md)
        for f in skills_dir.glob("*.py"):
            if f.name.startswith("_"):
                continue
            name = f.stem
            if name not in self.skills:
                skill = Skill(name=name, description=f"Skill: {name}")
                self._load_skill_module(skill, f)
                if skill.tools:
                    self.register(skill)

        logger.info(f"Loaded {len(self.skills)} skills, {len(self.tools)} tools total")

    def _load_skill_module(self, skill: Skill, filepath: Path):
        try:
            spec = importlib.util.spec_from_file_location(filepath.stem, filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "get_skill"):
                loaded = module.get_skill()
                skill.tools.update(loaded.tools)
                if not skill.description and loaded.description:
                    skill.description = loaded.description
            elif hasattr(module, "skill"):
                loaded = module.skill
                skill.tools.update(loaded.tools)
            elif hasattr(module, "tools"):
                skill.tools.update(module.tools)
            else:
                # Auto-detect: find callable functions that match tool names from SKILL.md
                # or any public functions (not starting with _)
                tool_names = set(skill.meta.tools) if skill.meta else set()
                for attr_name in dir(module):
                    if attr_name.startswith("_"):
                        continue
                    obj = getattr(module, attr_name)
                    if callable(obj) and not isinstance(obj, type):
                        # If SKILL.md lists tool names, only register those
                        if tool_names:
                            if attr_name in tool_names:
                                skill.tools[attr_name] = obj
                        else:
                            # No SKILL.md tool list — register all public functions
                            skill.tools[attr_name] = obj
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")


def create_skill(name: str, description: str, tools: Optional[Dict] = None) -> Skill:
    return Skill(name=name, description=description, tools=tools or {})


def register_builtin_skills(registry: SkillRegistry):
    """Register built-in skills."""
    def calc(expression: str, **kw) -> str:
        allowed = set("0123456789+-*/.() ")
        if all(c in allowed for c in expression):
            return str(eval(expression))
        return "Error: Invalid expression"

    def get_time(timezone: str = "", **kw) -> str:
        """Get current date/time, optionally in a specific timezone."""
        from datetime import datetime, timezone as tz, timedelta
        if timezone:
            m = re.match(r'UTC([+-]\d+)', timezone.upper())
            if m:
                offset = int(m.group(1))
                now = datetime.now(tz(timedelta(hours=offset)))
                return now.strftime(f"%Y-%m-%d %H:%M:%S (UTC{'+' if offset >= 0 else ''}{offset})")
        from datetime import datetime as dt
        return dt.now().strftime("%Y-%m-%d %H:%M:%S (local)")

    def safe_eval(code: str, **kw) -> str:
        """Execute simple Python expressions in a restricted sandbox."""
        import ast
        try:
            tree = ast.parse(code, mode='eval')
            # Only allow safe node types
            SAFE = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Str,
                    ast.List, ast.Tuple, ast.Dict, ast.Set, ast.Constant,
                    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
                    ast.FloorDiv, ast.USub, ast.UAdd, ast.Compare,
                    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
                    ast.BoolOp, ast.And, ast.Or, ast.Not, ast.IfExp,
                    ast.Call, ast.Name, ast.Attribute, ast.Subscript, ast.Index, ast.Slice)
            for node in ast.walk(tree):
                if not isinstance(node, SAFE):
                    return f"Error: unsafe expression ({type(node).__name__})"
            # Restricted builtins
            safe_builtins = {"abs": abs, "len": len, "min": min, "max": max,
                             "sum": sum, "round": round, "sorted": sorted,
                             "int": int, "float": float, "str": str, "bool": bool,
                             "list": list, "dict": dict, "set": set, "tuple": tuple,
                             "range": range, "enumerate": enumerate, "zip": zip,
                             "True": True, "False": False, "None": None}
            result = eval(compile(tree, '<expr>', 'eval'), {"__builtins__": {}}, safe_builtins)
            return str(result)
        except SyntaxError:
            return "Error: invalid syntax"
        except Exception as e:
            return f"Error: {e}"

    registry.register(create_skill("calculator", "Basic calculator", {"calc": calc}))
    registry.register(create_skill("datetime", "Date/time utilities", {"get_time": get_time}))
    registry.register(create_skill("python", "Safe Python eval", {"safe_eval": safe_eval}))

    # Translation skill (via LLM — returns prompt for LLM to translate)
    def translate(text: str, target_lang: str = "en", **kw) -> str:
        """Translate text. Returns instruction for LLM to process."""
        lang_map = {"en": "English", "zh": "中文", "ja": "日本語", "ko": "한국어",
                    "fr": "Français", "de": "Deutsch", "es": "Español", "ru": "Русский"}
        lang_name = lang_map.get(target_lang, target_lang)
        return f"[Translate to {lang_name}]: {text}"

    registry.register(create_skill("translate", "Translation via LLM", {"translate": translate}))


def test_skills():
    """Quick self-test."""
    # Test SKILL.md parsing
    md = """# GitHub Skill
GitHub操作：issues、PRs、CI等。

## read_when
github issue pr commit repository repo

## tools
- create_issue: Create a GitHub issue
- list_repos: List repositories
"""
    meta = parse_skill_md(md)
    assert meta.name == "GitHub Skill"
    assert "GitHub" in meta.description
    assert "github" in meta.read_when
    assert "create_issue" in meta.tools

    # Test activation
    assert should_activate(meta, "Create a GitHub issue please")
    assert should_activate(meta, "list my repos")
    assert not should_activate(meta, "what is the weather")

    # Test registry
    reg = SkillRegistry()
    register_builtin_skills(reg)
    assert "calculator" in reg.list_skills()
    assert reg.get_tool("calc") is not None

    # Test skill with meta
    skill = Skill(name="github", description="GitHub ops", meta=meta)
    reg.register(skill)
    activated = reg.activate_for_message("show me the github issues")
    assert len(activated) > 0

    print("  ✓ skills.py tests passed")


if __name__ == "__main__":
    test_skills()
