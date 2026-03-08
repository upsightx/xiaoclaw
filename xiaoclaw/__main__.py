"""xiaoclaw CLI entry point - python -m xiaoclaw"""
from .cli import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
