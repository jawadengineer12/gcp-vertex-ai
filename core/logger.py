import logging
import sys
from logging.handlers import RotatingFileHandler

from core.config import (
    PIPELINE_LOG_PATH,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
)


def setup_logging() -> None:
    """
    Configure root logging once for the whole pipeline.

    Logs are written to:
    - console
    - logs/pipeline.log
    """
    PIPELINE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    numeric_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        PIPELINE_LOG_PATH,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)

    root_logger.info("Logging initialized.")
    root_logger.info("Log file path: %s", PIPELINE_LOG_PATH)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
