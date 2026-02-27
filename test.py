#!/usr/bin/env python3
"""Test script for xiaoclaw"""
import asyncio
import sys
sys.path.insert(0, '/app')

from xiaoclaw.core import XiaClaw, XiaClawConfig, VERSION


async def test_core():
    print(f"=== Testing xiaoclaw v{VERSION} ===\n")

    config = XiaClawConfig(debug=True, security_level="strict")
    claw = XiaClaw(config)

    # Test 1: Tools
    print("Test 1: List tools")
    tools = claw.tools.list_names()
    print(f"  Tools: {tools}")
    assert len(tools) > 0, "No tools registered"
    print("  ✓ Pass\n")

    # Test 2: Read file
    print("Test 2: Read file")
    result = claw.tools.call("read", {"file_path": "/etc/hostname"})
    print(f"  Result: {result[:100]}")
    assert "Error" not in result or "not found" in result
    print("  ✓ Pass\n")

    # Test 3: Write file
    print("Test 3: Write file")
    result = claw.tools.call("write", {"file_path": "/tmp/test_xiaoclaw.txt", "content": "Hello from xiaoclaw!"})
    print(f"  Result: {result}")
    assert "Written" in result
    print("  ✓ Pass\n")

    # Test 4: Exec command
    print("Test 4: Exec command")
    result = claw.tools.call("exec", {"command": "echo 'xiaoclaw works!'"})
    print(f"  Result: {result}")
    assert "xiaoclaw works" in result
    print("  ✓ Pass\n")

    # Test 5: Security
    print("Test 5: Security check")
    assert claw.security.is_dangerous("rm -rf /")
    assert not claw.security.is_dangerous("ls")
    print("  ✓ Pass\n")

    # Test 6: Handle messages
    print("Test 6: Handle messages")
    for msg in ["你好", "工具列表"]:
        r = await claw.handle_message(msg)
        print(f"  > {msg}")
        print(f"  < {r[:200]}\n")

    # Test 7: Session
    print("Test 7: Session")
    assert len(claw.session.messages) > 0
    claw.session.save()
    sessions = claw.session_mgr.list_sessions()
    print(f"  Sessions: {len(sessions)}")
    print("  ✓ Pass\n")

    # Test 8: Module tests
    print("Test 8: Module self-tests")
    from xiaoclaw.providers import test_providers; test_providers()
    from xiaoclaw.session import test_session; test_session()
    from xiaoclaw.memory import test_memory; test_memory()
    from xiaoclaw.skills import test_skills; test_skills()
    print()

    # Test 9: Version
    print(f"Test 9: Version = {VERSION}")
    assert VERSION == "0.3.1"
    print("  ✓ Pass\n")

    print("=== All Tests Passed! ===")


if __name__ == "__main__":
    asyncio.run(test_core())
