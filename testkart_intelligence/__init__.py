"""Testkart Government Exam Intelligence & Publishing Multi-Agent System."""

import sys

# Prevent Python 3.13 Windows C-level _asyncio access violation (CPython 3.13 Windows bug)
if sys.platform == "win32" and sys.version_info >= (3, 13):
    sys.modules["_asyncio"] = None

__version__ = "0.1.0"
