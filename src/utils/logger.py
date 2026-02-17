"""Logging setup for Grant Hunter AI."""

import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str = "grant_hunter",
    log_level: str | None = None,
    log_dir: str = "logs",
) -> logging.Logger:
    """Set up and return a configured logger.

    Args:
        name: Logger name.
        log_level: Logging level string. Defaults to LOG_LEVEL env var or INFO.
        log_dir: Directory to store log files.
    """
    level = getattr(logging, (log_level or os.getenv("LOG_LEVEL", "INFO")).upper())
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(log_path / f"grant_hunter_{today}.log")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Error file handler
    error_handler = logging.FileHandler(log_path / f"errors_{today}.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    return logger
