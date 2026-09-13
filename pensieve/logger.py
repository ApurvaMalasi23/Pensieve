"""
pensieve/logger.py
------------------
Centralised logging configuration for the Pensieve pipeline.

All modules should import `get_logger` from here rather than calling
`logging.getLogger` directly, so that handler setup is guaranteed to
happen exactly once (when this module is first imported).

Usage
-----
    from pensieve.logger import get_logger
    log = get_logger(__name__)
    log.info("Processing %s", filename)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOG_FILE = Path("pensieve.log")
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_configured = False


def _configure() -> None:
    """Set up root logger handlers exactly once."""
    global _configured
    if _configured:
        return

    root = logging.getLogger("pensieve")
    root.setLevel(logging.DEBUG)

    # --- stderr handler (INFO and above) ---
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)
    stderr_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root.addHandler(stderr_handler)

    # --- file handler (DEBUG and above) ---
    try:
        file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        root.addHandler(file_handler)
    except OSError as exc:
        # Non-fatal: if the log file can't be opened (read-only FS, etc.)
        # we still have the stderr handler.
        root.warning("Could not open log file %s: %s", _LOG_FILE, exc)

    # Suppress chatty third-party loggers at DEBUG level.
    for noisy in ("httpx", "httpcore", "urllib3", "PIL", "pdfminer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'pensieve' namespace.

    Parameters
    ----------
    name:
        Typically ``__name__`` from the calling module.
    """
    _configure()
    # If name already starts with 'pensieve', use it as-is; otherwise
    # nest it so all loggers appear under the 'pensieve.*' hierarchy.
    if not name.startswith("pensieve"):
        name = f"pensieve.{name}"
    return logging.getLogger(name)
