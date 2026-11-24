"""Thread-safe rotating logger for MaxHotbox."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .constants import PLUGIN_NAME, SUPPORTED_MAX_VERSIONS

_LOGGER: logging.Logger | None = None


def get_running_max_year() -> int | None:
    """Return the running Autodesk 3ds Max product year (e.g. 2026 or 2027), or None offline."""
    try:
        from pymxs import runtime as rt  # type: ignore[import-not-found]

        mv = rt.maxVersion()
        if mv is not None:
            if len(mv) >= 8:
                year_val = int(mv[7])
                if 2000 <= year_val <= 2100:
                    return year_val
            if len(mv) >= 1:
                major = int(mv[0]) // 1000
                if major >= 10:
                    return 1998 + major
    except Exception:
        pass
    return None


def _get_live_max_data_dir() -> Path | None:
    """Ask the running 3ds Max instance directly for its user maxData directory."""
    try:
        from pymxs import runtime as rt  # type: ignore[import-not-found]

        raw = rt.getDir(rt.Name("maxData"))
        if raw:
            p = Path(str(raw))
            if p.is_dir():
                return p
    except Exception:
        pass
    return None


def get_user_data_dir() -> Path:
    """Resolve user-writable MaxHotbox data directory for 3ds Max 2026 / 2027 (CHS/ENU/etc.)."""
    # 1. Prefer the exact live 3ds Max user data dir (handles 2026, 2027, and any UI language).
    live_max_data = _get_live_max_data_dir()
    if live_max_data is not None:
        target = live_max_data / "userconfig" / PLUGIN_NAME
        try:
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError:
            pass

    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        # 2. Fallback: probe supported Max version directories (running year first, then newest).
        running_year = get_running_max_year()
        years: list[int] = []
        if running_year is not None:
            years.append(running_year)
        for y in sorted(SUPPORTED_MAX_VERSIONS, reverse=True):
            if y not in years:
                years.append(y)

        for year in years:
            max_root = Path(local_app) / "Autodesk" / "3dsMax" / f"{year} - 64bit"
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
