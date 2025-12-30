"""
Structured logging configuration for production use.

Uses structlog for JSON-formatted logs suitable for log aggregation systems.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor


def configure_logging(
    log_level: str = "INFO",
    json_logs: bool = True,
    service_name: str = "prediction-service",
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, output JSON format (production). If False, pretty console format (dev)
        service_name: Service name for log context
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    
    # Shared processors for all loggers
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # Merge context vars
        structlog.stdlib.add_log_level,  # Add log level
        structlog.stdlib.add_logger_name,  # Add logger name
        structlog.processors.TimeStamper(fmt="iso"),  # ISO timestamp
        structlog.processors.StackInfoRenderer(),  # Stack traces
    ]
    
    if json_logs:
        # Production: JSON format for log aggregation
        shared_processors.extend([
            structlog.processors.format_exc_info,  # Exception formatting
            structlog.processors.UnicodeDecoder(),  # Unicode handling
            structlog.processors.JSONRenderer(),  # JSON output
        ])
    else:
        # Development: Pretty console format
        shared_processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=True),  # Pretty colors
        ])
    
    # Configure structlog
    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Add service name to all logs
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def log_request(
    logger: structlog.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **kwargs: Any,
) -> None:
    """Log HTTP request with structured fields."""
    logger.info(
        "http_request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=round(duration_ms, 2),
        **kwargs,
    )


def log_error(
    logger: structlog.BoundLogger,
    error: Exception,
    context: dict[str, Any] | None = None,
) -> None:
    """Log error with full context."""
    logger.error(
        "error_occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        exc_info=True,
        **(context or {}),
    )


def log_prediction(
    logger: structlog.BoundLogger,
    game_id: str,
    home_team: str,
    away_team: str,
    model_version: str,
    **kwargs: Any,
) -> None:
    """Log prediction generation."""
    logger.info(
        "prediction_generated",
        game_id=game_id,
        home_team=home_team,
        away_team=away_team,
        model_version=model_version,
        **kwargs,
    )


def log_recommendation(
    logger: structlog.BoundLogger,
    game_id: str,
    bet_type: str,
    pick: str,
    edge: float,
    ev_percent: float,
    **kwargs: Any,
) -> None:
    """Log betting recommendation."""
    logger.info(
        "recommendation_generated",
        game_id=game_id,
        bet_type=bet_type,
        pick=pick,
        edge=round(edge, 2),
        ev_percent=round(ev_percent, 2),
        **kwargs,
    )

