"""Logging utilities for Scrapefruit."""

import logging
import sys
from pathlib import Path
from datetime import datetime

import config


def setup_logger(name: str = "scrapefruit") -> logging.Logger:
    """
    Set up and return a logger instance.

    Args:
        name: Logger name

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if config.FLASK_DEBUG else logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if config.FLASK_DEBUG else logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler
    log_file = config.LOGS_DIR / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger


# Default logger
logger = setup_logger()


def log_scrape(url: str, method: str, success: bool, time_ms: int, error: str = None):
    """Log a scrape attempt."""
    status = "✓" if success else "✗"
    msg = f"{status} [{method}] {url} ({time_ms}ms)"
    if error:
        msg += f" - {error}"

    if success:
        logger.info(msg)
    else:
        logger.warning(msg)


def log_job_start(job_id: str, name: str, url_count: int):
    """Log job start."""
    logger.info(f"Job started: {name} ({job_id[:8]}) - {url_count} URLs")


def log_job_complete(job_id: str, name: str, success: int, failed: int, duration_s: float):
    """Log job completion."""
    logger.info(
        f"Job completed: {name} ({job_id[:8]}) - "
        f"{success} success, {failed} failed, {duration_s:.1f}s"
    )
