"""
Shared logger for the atheriz game server.

Usage:
    from atheriz.logger import logger

    logger.info("Something happened")
    logger.warning("Watch out!")
    logger.error("Something went wrong")
"""

import logging

from atheriz import settings

# Create the shared logger
logger = logging.getLogger("atheriz")

# Set default level (will inherit uvicorn's handlers when server is running)
if settings.LOG_LEVEL == "debug":
    logger.setLevel(logging.DEBUG)
elif settings.LOG_LEVEL == "info":
    logger.setLevel(logging.INFO)
elif settings.LOG_LEVEL == "warning":
    logger.setLevel(logging.WARNING)
elif settings.LOG_LEVEL == "error":
    logger.setLevel(logging.ERROR)
elif settings.LOG_LEVEL == "critical":
    logger.setLevel(logging.CRITICAL)
else:
    logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s: %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
