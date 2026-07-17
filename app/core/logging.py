import logging
import sys
from typing import Any, Dict
import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings


def drop_color_message_key(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Uvicorn logs contain a color_message key that structlog ConsoleRenderer complains about.

    This processor drops it.
    """
    event_dict.pop("color_message", None)
    return event_dict


def setup_logging() -> None:
    # Define processors shared between standard logging and structlog
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        drop_color_message_key,
    ]

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Formatters
    if settings.ENVIRONMENT == "prod":
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=shared_processors,
        )

    # Stream Handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.LOG_LEVEL)

    # Adjust third-party loggers to prevent noise
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)


# Expose logger for application-wide import
logger = structlog.get_logger("app")
