"""xiaoclaw Battle System — 多角色辩论/协作引擎

多个角色（CEO、CTO、开发、QA等）针对同一问题各自给出观点，
最后由"主持人"汇总所有观点给出结论。
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger("xiaoclaw.Battle")


# ─── Role 定义 ────────────────────────────────────────

@dataclass
class Role:
    name: str
    system_prompt: str
    emoji: str = "💬"
    max_tokens: int = 300

    def build_messages(self, question: str) -> list:
        return [
            {"role": "system", "content": (
                f"{self.system_prompt}\n\n"
                f"请针对以下问题，从你的专业角度给出简洁观点（不超过200字，用中文回答）。"
                f"直接给出观点，不要重复问题，不要说'作为XX'这种开头。"
            )},
            {"role": "user", "content": question},
        ]


# ─── 预设角色 ─────────────────────────────────────────

PRESET_ROLES: Dict[str, Role] = {
    "ceo": Role(
        "CEO", "你是公司CEO，从战略全局角度思考，关注商业价值、ROI、市场竞争、长期发展", "👔"
    ),
    "cto": Role(
        "CTO", "你是CTO，从技术架构角度思考，关注可行性、技术债务、扩展性、安全性", "🔧"
    ),
    "pm": Role(
        "产品经理", "你是产品经理，从用户需求角度思考，关注用户体验、需求优先级、MVP策略", "📊"
    ),
    "dev": Role(
        "高级开发", "你是高级开发工程师，从实现角度思考，关注代码质量、工期估算、技术选型", "💻"
    ),
    "qa": Role(
        "QA", "你是QA工程师，从质量角度思考，关注边界情况、风险点、测试覆盖率", "🧪"
    ),
    "security": Role(
        "安全专家", "你是安全专家，从安全角度思考，关注漏洞、合规要求、数据保护", "🔒"
    ),
    "designer": Role(
        "设计师", "你是UI/UX设计师，从设计角度思考，关注用户体验、交互流程、视觉美观", "🎨"
    ),
    "devil": Role(
        "魔鬼代言人", "你是魔鬼代言人，专门挑毛病、找反例、质疑假设，确保方案经得起考验", "😈"
    ),
}

DEFAULT_BATTLE_ROLES = ["ceo", "cto", "dev", "qa"]

# ─── 主持人角色 ───────────────────────────────────────

MODERATOR_PROMPT = (
    "你是一位资深的讨论主持人。你的任务是汇总多位专家的观点，给出一个平衡、务实的最终结论。\n"
    "要求：\n"
    "1. 简要概括各方核心观点的共识和分歧\n"
    "2. 给出明确的建议和行动方案\n"
    "3. 不超过300字，用中文回答\n"
    "4. 直接给结论，不要说'综合各方观点'这种废话开头"
)


# ─── Battle Engine ────────────────────────────────────

class BattleEngine:
    """多角色辩论引擎，并发调用LLM获取各角色观点后汇总。"""

    def __init__(self, provider):
        """
        Args:
            provider: Provider instance with .client and .current_model
        """
        self.provider = provider

    async def _call_role(self, role: Role, question: str) -> Dict[str, str]:
        """调用单个角色获取观点。"""
        messages = role.build_messages(question)
        try:
            resp = await self.provider.client.chat.completions.create(
                model=self.provider.current_model,
                messages=messages,
                max_tokens=role.max_tokens,
            )
            content = resp.choices[0].message.content or ""
            # 清理 <think> 标签
            import re
            content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL).strip()
            return {"name": role.name, "emoji": role.emoji, "content": content}
        except Exception as e:
            logger.error(f"Role '{role.name}' failed: {e}")
            return {"name": role.name, "emoji": role.emoji, "content": f"[调用失败: {e}]"}

    async def _call_moderator(self, question: str, opinions: List[Dict[str, str]]) -> str:
        """主持人汇总所有观点。"""
        opinion_text = "\n\n".join(
            f"【{o['name']}】: {o['content']}" for o in opinions
        )
        messages = [
            {"role": "system", "content": MODERATOR_PROMPT},
            {"role": "user", "content": (
                f"讨论主题: {question}\n\n"
                f"各方观点:\n{opinion_text}\n\n"
                f"请给出最终结论和建议。"
            )},
        ]
        try:
            resp = await self.provider.client.chat.completions.create(
                model=self.provider.current_model,
                messages=messages,
                max_tokens=500,
            )
            content = resp.choices[0].message.content or ""
            import re
            content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            logger.error(f"Moderator failed: {e}")
            return f"[主持人汇总失败: {e}]"

    async def battle(
        self,
        question: str,
        role_keys: Optional[List[str]] = None,
        custom_roles: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        执行多角色辩论。

        Args:
            question: 辩论主题
            role_keys: 预设角色key列表，如 ["ceo","cto","dev"]
            custom_roles: 自定义角色列表，如 [{"name":"投资人","prompt":"从投资角度分析"}]

        Returns:
            {"question": str, "opinions": [...], "conclusion": str, "formatted": str}
        """
        roles: List[Role] = []

        # 收集预设角色
        if role_keys:
            for key in role_keys:
                key = key.strip().lower()
                if key in PRESET_ROLES:
                    roles.append(PRESET_ROLES[key])
                else:
                    logger.warning(f"Unknown role: {key}, skipping")

        # 收集自定义角色
        if custom_roles:
            for cr in custom_roles:
                name = cr.get("name", "自定义角色")
                prompt = cr.get("prompt", "请从你的角度分析问题")
                emoji = cr.get("emoji", "🎭")
                roles.append(Role(name=name, system_prompt=prompt, emoji=emoji))

        # 默认角色
        if not roles:
            roles = [PRESET_ROLES[k] for k in DEFAULT_BATTLE_ROLES]

        # 并发调用所有角色
        tasks = [self._call_role(role, question) for role in roles]
        opinions = await asyncio.gather(*tasks)

        # 主持人汇总
        conclusion = await self._call_moderator(question, opinions)

        # 格式化输出
        formatted = format_battle_output(question, opinions, conclusion)

        return {
            "question": question,
            "opinions": list(opinions),
            "conclusion": conclusion,
            "formatted": formatted,
        }


# ─── 格式化输出 ───────────────────────────────────────

def format_battle_output(
    question: str,
    opinions: List[Dict[str, str]],
    conclusion: str,
) -> str:
    """格式化battle结果为好看的文本。"""
    lines = [f"\n🏢 Battle: \"{question}\"\n"]
    lines.append("─" * 40)
    for o in opinions:
        lines.append(f"\n{o['emoji']} {o['name']}:")
        lines.append(f"  {o['content']}")
    lines.append("\n" + "─" * 40)
    lines.append(f"\n📋 结论:\n  {conclusion}")
    lines.append("")
    return "\n".join(lines)


def list_preset_roles() -> str:
    """列出所有预设角色。"""
    lines = ["🏢 预设角色列表:\n"]
    for key, role in PRESET_ROLES.items():
        lines.append(f"  {role.emoji} {key:10s} — {role.name}: {role.system_prompt[:50]}...")
    lines.append(f"\n默认组合: {', '.join(DEFAULT_BATTLE_ROLES)}")
    lines.append("用法: /battle <问题>  或  /battle-custom ceo,dev,devil <问题>")
    return "\n".join(lines)


# ─── 工具函数（供 ToolRegistry 调用）─────────────────

def tool_battle(question: str = "", roles: str = "", **kw) -> str:
    """同步包装：执行预设角色battle。供tools.py注册使用。"""
    if not question:
        return "Error: question is required"
    role_keys = [r.strip() for r in roles.split(",") if r.strip()] if roles else None
    # 需要在调用时注入provider，这里返回配置信息
    return _sync_placeholder(question, role_keys=role_keys)


def tool_battle_custom(question: str = "", roles_json: str = "", **kw) -> str:
    """同步包装：执行自定义角色battle。"""
    if not question:
        return "Error: question is required"
    import json
    try:
        custom_roles = json.loads(roles_json) if roles_json else []
    except Exception:
        return "Error: roles_json must be valid JSON array, e.g. [{\"name\":\"投资人\",\"prompt\":\"从投资角度分析\"}]"
    return _sync_placeholder(question, custom_roles=custom_roles)


def _sync_placeholder(question, role_keys=None, custom_roles=None):
    """占位：实际执行在 BattleToolWrapper 中。"""
    return "Error: battle engine not initialized"


class BattleToolWrapper:
    """包装battle工具，持有provider引用以便同步调用。"""

    def __init__(self, provider):
        self.engine = BattleEngine(provider)

    def battle(self, question: str = "", roles: str = "", **kw) -> str:
        if not question:
            return "Error: question is required"
        role_keys = [r.strip() for r in roles.split(",") if r.strip()] if roles else None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        lambda: asyncio.run(self.engine.battle(question, role_keys=role_keys))
                    ).result(timeout=120)
            else:
                result = loop.run_until_complete(
                    self.engine.battle(question, role_keys=role_keys)
                )
            return result["formatted"]
        except Exception as e:
            return f"Battle failed: {e}"

    def battle_custom(self, question: str = "", roles_json: str = "", **kw) -> str:
        if not question:
            return "Error: question is required"
        import json
        try:
            custom_roles = json.loads(roles_json) if roles_json else []
        except Exception:
            return "Error: roles_json must be valid JSON array"
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        lambda: asyncio.run(self.engine.battle(question, custom_roles=custom_roles))
                    ).result(timeout=120)
            else:
                result = loop.run_until_complete(
                    self.engine.battle(question, custom_roles=custom_roles)
                )
            return result["formatted"]
        except Exception as e:
            return f"Battle failed: {e}"
