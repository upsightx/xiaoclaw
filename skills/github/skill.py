#!/usr/bin/env python3
"""GitHub Skill"""
import subprocess
def gh_run(command: str, **kwargs) -> str:
    try:
        r = subprocess.run(f"gh {command}", shell=True, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr)[:5000]
    except Exception as e: return str(e)
def get_skill():
    from xiaoclaw.skills import create_skill
    return create_skill("github", "GitHub操作", {"gh": gh_run})
skill = get_skill()
