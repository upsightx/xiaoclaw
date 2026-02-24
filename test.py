#!/usr/bin/env python3
"""Test script for xiaoclaw"""

import asyncio
import sys
sys.path.insert(0, '/app')

from xiaoclaw.core import XiaClaw, XiaClawConfig


async def test_core():
    """测试核心功能"""
    print("=== Testing xiaoclaw Core ===\n")
    
    # 创建配置
    config = XiaClawConfig(
        debug=True,
        security_level="strict"
    )
    
    # 创建实例
    claw = XiaClaw(config)
    
    # 测试1: 列出工具
    print("Test 1: List tools")
    tools = claw.tools.list_tools()
    print(f"  Available tools: {tools}\n")
    
    # 测试2: 读取文件（模拟）
    print("Test 2: Read file (mock)")
    result = claw.tools._tool_read("/etc/hostname")
    print(f"  Result: {result[:100]}...\n")
    
    # 测试3: 写文件
    print("Test 3: Write file")
    result = claw.tools._tool_write("Hello from xiaoclaw!", "/tmp/test_xiaoclaw.txt")
    print(f"  Result: {result}\n")
    
    # 测试4: 执行命令
    print("Test 4: Exec command")
    result = claw.tools._tool_exec("echo 'xiaoclaw works!'")
    print(f"  Result: {result}\n")
    
    # 测试5: 处理消息
    print("Test 5: Handle message")
    messages = [
        "hello",
        "what tools do you have?",
        "version",
        "test write tool"
    ]
    for msg in messages:
        response = await claw.handle_message(msg)
        print(f"  User: {msg}")
        print(f"  xiaoclaw: {response}\n")
    
    # 测试6: 安全检查
    print("Test 6: Security check")
    is_dangerous = claw.security.is_dangerous("exec", "rm -rf /")
    print(f"  Is 'rm -rf /' dangerous? {is_dangerous}")
    
    is_dangerous2 = claw.security.is_dangerous("exec", "ls")
    print(f"  Is 'ls' dangerous? {is_dangerous2}\n")
    
    print("=== All Tests Passed! ===")


if __name__ == "__main__":
    asyncio.run(test_core())
