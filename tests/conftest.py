"""Pytest test suite configuration."""

import sys
if sys.platform == "win32" and sys.version_info >= (3, 13):
    sys.modules["_asyncio"] = None

import logging

# Prevent Python 3.13 Windows asyncio task name logging crash
logging.logAsyncioTasks = False
