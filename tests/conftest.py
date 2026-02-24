"""pytest configuration for xiaoclaw tests"""
import sys
from pathlib import Path

# Ensure xiaoclaw is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
