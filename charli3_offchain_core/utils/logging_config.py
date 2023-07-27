"""Logging configuration."""
import logging
from logging.config import dictConfig

LEVEL_COLORS = [
    "\033[0m",  # No Set
    "\033[36m",  # Debug
    "\033[34m",  # Info
    "\033[33m",  # Warning
    "\033[31m",  # Error
    "\033[1;31m",  # Critical
]

LOG_FORMAT = (
    "%(level_color)s[%(name)s:%(levelname)s]%(end_color)s [%(asctime)s] %(message)s"
)


def get_log_config(log_level=logging.INFO):
    """get log_config."""
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": LOG_FORMAT,
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                "level": log_level,
                "level_colors": LEVEL_COLORS,
            },
            "json": {
                "format": "%(asctime)s %(name)s %(levelname)s %(message)fs",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            },
        },
        "handlers": {
            "standard": {"class": "logging.StreamHandler", "formatter": "standard"}
        },
        "loggers": {"": {"handlers": ["standard"], "level": log_level}},
    }

    return log_config


logconfig = get_log_config(logging.INFO)
dictConfig(logconfig)

old_factory = logging.getLogRecordFactory()


def _record_factory(*args, **kwargs):
    record = old_factory(*args, **kwargs)
    record.level_color = LEVEL_COLORS[record.levelno // 10]
    record.end_color = "\033[0m"
    return record


logging.setLogRecordFactory(_record_factory)
