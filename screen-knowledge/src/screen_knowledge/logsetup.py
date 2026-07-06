"""Rotating file logger for the daemon (logs/daemon.log)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from . import paths

_configured = False


def get_logger() -> logging.Logger:
    """Return the package logger, configuring a rotating file handler once."""
    global _configured
    logger = logging.getLogger("screen_knowledge")
    if not _configured:
        logger.setLevel(logging.INFO)
        try:
            paths.logs_dir().mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                paths.logs_dir() / "daemon.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
            logger.addHandler(handler)
        except Exception:
            # Never let logging setup crash the daemon; fall back to stderr.
            logger.addHandler(logging.StreamHandler())
        _configured = True
    return logger
