#!/usr/bin/env python3
"""xiaoclaw Documentation Generator — auto-generate API docs from source"""
import ast
import sys
from pathlib import Path
from typing import List, Dict


def extract_module_info(filepath: Path) -> Dict:
    """Extract classes, functions, and docstrings from a Python file."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as e:
        return {"file": str(filepath), "error": str(e)}

    info = {
        "file": str(filepath),
        "module_doc": ast.get_docstring(tree) or "",
        "classes": [],
        "functions": [],
    }

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            cls = {
                "name": node.name,
                "doc": ast.get_docstring(node) or "",
                "methods": [],
                "line": node.lineno,
            }
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = [a.arg for a in item.args.args if a.arg != "self"]
                    cls["methods"].append({
                        "name": item.name,
                        "args": args,
                        "doc": ast.get_docstring(item) or "",
                        "async": isinstance(item, ast.AsyncFunctionDef),
                        "line": item.lineno,
                    })
            info["classes"].append(cls)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args if a.arg != "self"]
            info["functions"].append({
                "name": node.name,
                "args": args,
                "doc": ast.get_docstring(node) or "",
                "async": isinstance(node, ast.AsyncFunctionDef),
                "line": node.lineno,
            })

    return info


def generate_markdown(modules: List[Dict]) -> str:
    """Generate markdown documentation from extracted module info."""
    lines = ["# xiaoclaw API Reference\n", "Auto-generated documentation.\n"]

    for mod in modules:
        if "error" in mod:
            continue
        fname = Path(mod["file"]).name
        lines.append(f"\n## {fname}\n")
        if mod["module_doc"]:
            lines.append(f"{mod['module_doc']}\n")

        for cls in mod["classes"]:
            lines.append(f"\n### class `{cls['name']}`\n")
            if cls["doc"]:
                lines.append(f"{cls['doc']}\n")
            public_methods = [m for m in cls["methods"] if not m["name"].startswith("_")]
            if public_methods:
                lines.append("| Method | Args | Description |")
                lines.append("|--------|------|-------------|")
                for m in public_methods:
                    prefix = "async " if m["async"] else ""
                    args_str = ", ".join(m["args"][:4])
                    doc = m["doc"].split("\n")[0] if m["doc"] else ""
                    lines.append(f"| `{prefix}{m['name']}` | `{args_str}` | {doc} |")
                lines.append("")

        public_funcs = [f for f in mod["functions"] if not f["name"].startswith("_")]
        if public_funcs:
            lines.append("\n#### Functions\n")
            for f in public_funcs:
                prefix = "async " if f["async"] else ""
                args_str = ", ".join(f["args"][:4])
                lines.append(f"- `{prefix}{f['name']}({args_str})` — {f['doc'].split(chr(10))[0] if f['doc'] else ''}")
            lines.append("")

    return "\n".join(lines)


def generate_docs(src_dir: str = "xiaoclaw", output: str = "docs/API.md"):
    """Generate documentation for all modules."""
    src = Path(src_dir)
    modules = []
    for f in sorted(src.rglob("*.py")):
        if f.name.startswith("_") and f.name != "__init__.py":
            continue
        info = extract_module_info(f)
        if info.get("classes") or info.get("functions"):
            modules.append(info)

    md = generate_markdown(modules)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"📄 Generated {output} ({len(modules)} modules, {len(md)} chars)")
    return md


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "xiaoclaw"
    out = sys.argv[2] if len(sys.argv) > 2 else "docs/API.md"
    generate_docs(src, out)
