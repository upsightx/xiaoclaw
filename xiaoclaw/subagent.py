"""xiaoclaw Sub-agent System — spawn independent agent instances for parallel tasks"""
import asyncio
import logging
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("xiaoclaw.Subagent")


@dataclass
class SubagentResult:
    task_id: str
    task: str
    status: str = "pending"  # pending, running, done, error
    result: str = ""
    error: str = ""


class SubagentManager:
    """Manages sub-agent instances for parallel task execution."""

    def __init__(self):
        self._tasks: Dict[str, SubagentResult] = {}
        self._running: Dict[str, asyncio.Task] = {}

    def list_tasks(self) -> list:
        return [
            {"task_id": t.task_id, "task": t.task[:80], "status": t.status}
            for t in self._tasks.values()
        ]

    def get_result(self, task_id: str) -> Optional[SubagentResult]:
        return self._tasks.get(task_id)

    async def spawn(self, task: str, claw_factory, model: str = None) -> str:
        """Spawn a sub-agent to execute a task.

        Args:
            task: The task description for the sub-agent
            claw_factory: A callable that creates a new XiaClaw instance
            model: Optional model override

        Returns:
            task_id for tracking
        """
        task_id = str(uuid.uuid4())[:8]
        result = SubagentResult(task_id=task_id, task=task, status="running")
        self._tasks[task_id] = result

        async def _run():
            try:
                claw = claw_factory()
                if model and claw.providers.active:
                    claw.providers.active.current_model = model

                # Give the sub-agent a focused system prompt
                sub_prompt = (
                    f"You are a sub-agent of xiaoclaw. Your task:\n{task}\n\n"
                    f"Complete this task and provide a clear, concise result. "
                    f"You have access to all tools. Be efficient."
                )
                claw.session.add_message("user", task)

                # Run through the agent loop
                parts = []
                async for chunk in claw._agent_loop(sub_prompt, stream=False):
                    parts.append(chunk)

                result.result = "".join(parts)
                result.status = "done"
            except Exception as e:
                result.error = str(e)
                result.status = "error"
                logger.error(f"Subagent {task_id} failed: {e}")

        atask = asyncio.create_task(_run())
        self._running[task_id] = atask
        return task_id

    async def wait(self, task_id: str, timeout: float = 60) -> SubagentResult:
        """Wait for a sub-agent to complete."""
        atask = self._running.get(task_id)
        if atask:
            try:
                await asyncio.wait_for(atask, timeout=timeout)
            except asyncio.TimeoutError:
                result = self._tasks.get(task_id)
                if result:
                    result.status = "error"
                    result.error = "Timed out"
        return self._tasks.get(task_id, SubagentResult(task_id=task_id, task="", status="error", error="Not found"))

    async def spawn_and_wait(self, task: str, claw_factory, model: str = None, timeout: float = 60) -> str:
        """Spawn a sub-agent and wait for the result."""
        task_id = await self.spawn(task, claw_factory, model)
        result = await self.wait(task_id, timeout)
        if result.status == "done":
            return result.result
        return f"[Subagent error: {result.error}]"

    def cancel(self, task_id: str) -> bool:
        """Cancel a running sub-agent."""
        atask = self._running.get(task_id)
        if atask and not atask.done():
            atask.cancel()
            result = self._tasks.get(task_id)
            if result:
                result.status = "error"
                result.error = "Cancelled"
            return True
        return False
