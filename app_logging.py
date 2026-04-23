from __future__ import annotations

import json
import logging
from typing import Any


LOGGER_NAME = "daily_ai_digest"


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    real_handlers = [
        handler for handler in logger.handlers if not isinstance(handler, logging.NullHandler)
    ]
    if not real_handlers:
        logger.handlers = []
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s %(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def structured_message(message: str, **fields: Any) -> str:
    if not fields:
        return message
    return f"{message}: {json.dumps(fields, sort_keys=True, default=str)}"


def log_event(level: int, message: str, **fields: Any) -> None:
    get_logger().log(level, structured_message(message, **fields))


def info(message: str, **fields: Any) -> None:
    log_event(logging.INFO, message, **fields)


def warning(message: str, **fields: Any) -> None:
    log_event(logging.WARNING, message, **fields)
