import logging
import sys
from app.config import get_settings


def configure_logging() -> None:
    """
    Configure structured logging for the application.
    Called once at startup in main.py lifespan.
    Log level is read from settings (LOG_LEVEL env var).
    """
    settings = get_settings()
    log_level = getattr(logging, settings.log_level, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers to avoid duplicate output
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if settings.is_production:
        # Production: compact single-line format for log aggregators
        fmt = (
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    else:
        # Development: human-readable format with module context
        fmt = (
            "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s"
        )

    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Convenience wrapper — returns a named logger.
    Usage: logger = get_logger(__name__)
    """
    return logging.getLogger(name)
