"""Thread-safe rotating logger for MaxHotbox."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .constants import PLUGIN_NAME

_LOGGER: logging.Logger | None = None


def get_user_data_dir() -> Path:
    """Resolve user-writable MaxHotbox data directory (works on both CHS and ENU Max 2026)."""
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        # Prefer Max 2026 user dir if present (check both CHS and ENU), else %LOCALAPPDATA%\MaxHotbox
        max_root = Path(local_app) / "Autodesk" / "3dsMax" / "2026 - 64bit"
        for lang in ("CHS", "ENU"):
            lang_dir = max_root / lang
            if lang_dir.is_dir():
                target = lang_dir / "userconfig" / PLUGIN_NAME
                try:
                    target.mkdir(parents=True, exist_ok=True)
                    return target
                except OSError:
                    pass

        generic = Path(local_app) / PLUGIN_NAME
        try:
            generic.mkdir(parents=True, exist_ok=True)
            return generic
        except OSError:
            pass

    fallback = Path.home() / f".{PLUGIN_NAME.lower()}"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_logger() -> logging.Logger:
    """Return the singleton MaxHotbox logger."""
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger(PLUGIN_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        try:
            log_dir = get_user_data_dir() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "max_hotbox.log"
            handler = RotatingFileHandler(
                str(log_file),
                maxBytes=512 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        except OSError:
            logger.addHandler(logging.NullHandler())

    _LOGGER = logger
    return logger
