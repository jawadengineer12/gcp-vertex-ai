# core/logger.py
import logging
import sys
from logging.handlers import RotatingFileHandler

from core.config import (
    PIPELINE_LOG_PATH,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
)


def setup_logging(hosted: bool = False) -> None:
    """
    Configure root logging once for the whole pipeline.
    CLI logs go to stdout and a rotating file; hosted logs use stdout only.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    root_logger = logging.getLogger()

    if root_logger.handlers:
        return  # Already configured — skip

    numeric_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    formatter = (
        logging.Formatter("%(message)s")
        if hosted
        else logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    # Rotating file handler
    root_logger.addHandler(console_handler)
    if not hosted:
        PIPELINE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            PIPELINE_LOG_PATH,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)

    if not hosted:
        root_logger.info("Logging initialized.")
        root_logger.info("Log file: %s", PIPELINE_LOG_PATH)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
