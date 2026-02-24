#!/usr/bin/env python3
"""
XiaClaw - Lightweight AI Agent
Minimal Core Design with Security First
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("XiaClaw")

# 版本
VERSION = "0.1.0"

@dataclass
class XiaClawConfig:
    """XiaClaw配置"""
    # 核心配置
    debug: bool = False
    
    # 安全配置
    security_level: str = "strict"  # strict, normal, relaxed
    require_confirm_dangerous: bool = True
    
    # 消息配置
    channels: List[str] = field(default_factory=lambda: ["feishu", "telegram"])
    
    # 模型配置
    default_model: str = "minimax/MiniMax-M2.5"
    api_key: str = ""
    base_url: str = "https://api.minimax.chat/v1"
    
    # 工具配置
    enabled_tools: List[str] = field(default_factory=lambda: ["read", "write", "exec", "web_search"])
    
    @classmethod
    def from_env(cls) -> "XiaClawConfig":
        """从环境变量加载配置"""
        return cls(
            debug=os.getenv("XIAOCLAW_DEBUG", "false").lower() == "true",
            security_level=os.getenv("XIAOCLAW_SECURITY", "strict"),
            require_confirm_dangerous=os.getenv("XIAOCLAW_CONFIRM_DANGEROUS", "true").lower() == "true",
            api_key=os.getenv("OPENAI_API_KEY", os.getenv("MINIMAX_API_KEY", "")),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.minimax.chat/v1"),
            default_model=os.getenv("XIAOCLAW_MODEL", "minimax/MiniMax-M2.5"),
        )

# 危险操作列表
DANGEROUS_OPERATIONS = {
    "exec": ["rm", "del", "format", "dd", "mkfs", "fdisk"],
    "write": ["~/.ssh", "~/.gnupg", "~/.aws", "*.key", "*.pem", "*.p12"],
    "http": ["delete", "destroy", "remove"],
}


class SecurityManager:
    """安全管理器"""
    
    def __init__(self, config: XiaClawConfig):
        self.config = config
        self.pending_confirmations: Dict[str, dict] = {}
    
    def is_dangerous(self, tool: str, action: str, target: str = "") -> bool:
        """检查操作是否危险"""
        if self.config.security_level == "relaxed":
            return False
        
        # 检查危险操作列表
        if tool in DANGEROUS_OPERATIONS:
            dangerous_patterns = DANGEROUS_OPERATIONS.get(tool, [])
            for pattern in dangerous_patterns:
                if pattern.lower() in action.lower() or pattern in target:
                    return True
        
        # 检查敏感路径
        sensitive_paths = ["~/.ssh", "~/.gnupg", "~/.aws", "/etc/passwd"]
        for path in sensitive_paths:
            if path in target:
                return True
        
        return False
    
    def should_confirm(self, tool: str, action: str, target: str = "") -> bool:
        """是否需要确认"""
        if not self.config.require_confirm_dangerous:
            return False
        return self.is_dangerous(tool, action, target)


class ToolRegistry:
    """工具注册表 - 兼容OpenClaw生态"""
    
    def __init__(self):
        self.tools: Dict[str, Any] = {}
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """注册内置工具 - 与OpenClaw兼容"""
        # 文件操作
        self.register("read", self._tool_read, {
            "description": "Read file contents",
            "params": {"file_path": "string"}
        })
        
        self.register("write", self._tool_write, {
            "description": "Write content to file",
            "params": {"content": "string", "file_path": "string"}
        })
        
        self.register("edit", self._tool_edit, {
            "description": "Edit file content",
            "params": {"file_path": "string", "old_string": "string", "new_string": "string"}
        })
        
        # 执行
        self.register("exec", self._tool_exec, {
            "description": "Execute shell commands",
            "params": {"command": "string"}
        })
        
        # 网络
        self.register("web_search", self._tool_web_search, {
            "description": "Search the web",
            "params": {"query": "string", "count": "number"}
        })
        
        self.register("web_fetch", self._tool_web_fetch, {
            "description": "Fetch webpage content",
            "params": {"url": "string", "maxChars": "number"}
        })
        
        logger.info(f"Registered {len(self.tools)} builtin tools")
    
    def register(self, name: str, func: callable, meta: dict):
        """注册工具"""
        self.tools[name] = {
            "func": func,
            "meta": meta
        }
        logger.debug(f"Registered tool: {name}")
    
    def get_tool(self, name: str) -> Optional[dict]:
        """获取工具"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self.tools.keys())
    
    # 工具实现
    def _tool_read(self, file_path: str, **kwargs) -> str:
        """读取文件"""
        path = Path(file_path).expanduser()
        if not path.exists():
            return f"Error: File not found: {file_path}"
        try:
            content = path.read_text(encoding='utf-8')
            return content[:10000]  # 限制返回大小
        except Exception as e:
            return f"Error reading file: {e}"
    
    def _tool_write(self, content: str, file_path: str, **kwargs) -> str:
        """写入文件"""
        path = Path(file_path).expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return f"Success: Written to {file_path}"
        except Exception as e:
            return f"Error writing file: {e}"
    
    def _tool_edit(self, file_path: str, old_string: str, new_string: str, **kwargs) -> str:
        """编辑文件"""
        path = Path(file_path).expanduser()
        if not path.exists():
            return f"Error: File not found: {file_path}"
        try:
            content = path.read_text(encoding='utf-8')
            if old_string not in content:
                return "Error: old_string not found in file"
            content = content.replace(old_string, new_string)
            path.write_text(content, encoding='utf-8')
            return f"Success: Edited {file_path}"
        except Exception as e:
            return f"Error editing file: {e}"
    
    def _tool_exec(self, command: str, **kwargs) -> str:
        """执行命令"""
        import subprocess
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            return output[:5000] if output else "Command executed (no output)"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out"
        except Exception as e:
            return f"Error executing command: {e}"
    
    def _tool_web_search(self, query: str, count: int = 5, **kwargs) -> str:
        """网页搜索 - 模拟实现"""
        return f"[Mock] Web search for: {query} (count: {count})"
    
    def _tool_web_fetch(self, url: str, maxChars: int = 5000, **kwargs) -> str:
        """获取网页 - 模拟实现"""
        return f"[Mock] Fetched {maxChars} chars from: {url}"


class XiaClaw:
    """XiaClaw核心引擎"""
    
    def __init__(self, config: Optional[XiaClawConfig] = None):
        self.config = config or XiaClawConfig.from_env()
        self.security = SecurityManager(self.config)
        self.tools = ToolRegistry()
        self.running = False
        
        logger.info(f"XiaClaw v{VERSION} initialized")
        logger.info(f"Security level: {self.config.security_level}")
    
    def get_system_prompt(self) -> str:
        """获取系统提示 - 与OpenClaw兼容"""
        return f"""你是 XiaClaw，一个轻量级AI助手。

## 关于你
- 名字: XiaClaw
- 版本: {VERSION}
- 设计理念: 精简、安全、高效

## 可用工具
{', '.join(self.tools.list_tools())}

## 安全规则
- 默认禁止危险操作
- 敏感操作需要确认
- 不执行未明确要求的任务

## 记忆
- 短期记忆: 当前对话
- 长期记忆: /root/.openclaw/workspace/memory/

保持简洁、专业、高效。"""
    
    async def handle_message(self, message: str, context: dict = None) -> str:
        """处理消息"""
        logger.info(f"Received message: {message[:50]}...")
        
        # 简单响应（实际需要接入LLM）
        if "hello" in message.lower() or "你好" in message:
            return f"你好！我是 XiaClaw v{VERSION}，有什么可以帮你的？"
        
        if "tools" in message.lower() or "工具" in message.lower():
            return f"可用工具: {', '.join(self.tools.list_tools())}"
        
        if "version" in message.lower() or "版本" in message.lower():
            return f"XiaClaw v{VERSION} - 精简版AI助手"
        
        return f"收到消息: {message[:100]}... (XiaClaw v{VERSION})"
    
    def run(self):
        """运行XiaClaw"""
        self.running = True
        logger.info(f"XiaClaw v{VERSION} started!")
        logger.info(f"Tools: {self.tools.list_tools()}")
        logger.info(f"Channels: {self.config.channels}")


async def main():
    """主函数"""
    print(f"""
╔═══════════════════════════════════════╗
║         XiaClaw v{VERSION}                 ║
║    Lightweight AI Agent               ║
║    Security First                     ║
╚═══════════════════════════════════════╝
    """)
    
    # 加载配置
    config = XiaClawConfig.from_env()
    
    # 创建实例
    claw = XiaClaw(config)
    
    # 启动
    claw.run()
    
    # 测试消息
    test_messages = [
        "hello",
        "what tools do you have?",
        "version",
    ]
    
    print("\n--- Testing ---")
    for msg in test_messages:
        response = await claw.handle_message(msg)
        print(f"User: {msg}")
        print(f"XiaClaw: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
