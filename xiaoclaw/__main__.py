"""XiaClaw CLI entry point - resolves RuntimeWarning for python -m xiaoclaw.core"""
from .core import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
