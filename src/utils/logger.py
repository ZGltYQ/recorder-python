"""Logging configuration for the Audio Recorder application."""

import logging
import sys
from pathlib import Path
from typing import Optional
import structlog
from appdirs import user_log_dir


def setup_logging(
    app_name: str = "recorder-python", level: int = logging.INFO, log_to_file: bool = True
) -> structlog.BoundLogger:
    """Configure structured logging for the application."""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if log_to_file else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger(app_name)

    # Add file handler if requested
    if log_to_file:
        log_dir = Path(user_log_dir(app_name))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)

        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

        logger.info("Logging to file", log_file=str(log_file))

    return logger


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)
