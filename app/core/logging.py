"""
Structured logging configuration for SplitsenseAI.
Uses JSON format for production, readable format for development.
"""

import logging
import sys
from app.core.config import get_settings


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    settings = get_settings()

    logger = logging.getLogger("splitsenseai")
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    if settings.APP_ENV == "production":
        # JSON format for production (structured logging)
        formatter = logging.Formatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", '
            '"module": "%(module)s", "message": "%(message)s"}'
        )
    else:
        # Readable format for development
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s"
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


# Module-level logger instance
logger = setup_logging()
