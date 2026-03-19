"""
Structured Logging Module for Jira Allocation Connector.

This module configures structlog with JSON output for consistent,
machine-readable logging across the application.

Log Levels:
- ERROR: Auth failures, API errors, unhandled exceptions
- WARNING: Rate limiting, cache miss, incomplete data
- INFO: Connection established, sync complete, metrics calculated
- DEBUG: Request details, cache operations, intermediate calculations
"""

import logging
import sys
from enum import Enum
from typing import Optional

import structlog


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# Default configuration
_configured = False


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    json_output: bool = True,
    log_file: Optional[str] = None
) -> None:
    """
    Configure structlog with JSON output and appropriate processors.
    
    Args:
        level: Minimum log level to output
        json_output: If True, output JSON format; if False, output human-readable
        log_file: Optional file path to write logs to
    """
    global _configured
    
    # Set up standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.value),
    )
    
    # Configure file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.value))
        logging.getLogger().addHandler(file_handler)
    
    # Define processors based on output format
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_output:
        # JSON output for production/machine parsing
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Human-readable output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    _configured = True


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured structlog logger.
    
    Args:
        name: Optional logger name (defaults to calling module)
        
    Returns:
        Configured structlog BoundLogger instance
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("connection_established", server="jira.example.com")
        >>> logger.error("auth_failed", reason="invalid_token")
    """
    global _configured
    
    # Auto-configure with defaults if not already configured
    if not _configured:
        configure_logging()
    
    return structlog.get_logger(name)


# Pre-defined log event helpers for common scenarios
def log_auth_error(logger: structlog.stdlib.BoundLogger, error_message: str, **kwargs) -> None:
    """Log authentication error (ERROR level)."""
    logger.error("auth_error", error=error_message, **kwargs)


def log_api_error(logger: structlog.stdlib.BoundLogger, endpoint: str, status_code: int, error: str, **kwargs) -> None:
    """Log API error (ERROR level)."""
    logger.error("api_error", endpoint=endpoint, status_code=status_code, error=error, **kwargs)


def log_rate_limit(logger: structlog.stdlib.BoundLogger, retry_after: int, attempt: int, **kwargs) -> None:
    """Log rate limiting warning (WARNING level)."""
    logger.warning("rate_limited", retry_after_seconds=retry_after, attempt=attempt, **kwargs)


def log_cache_miss(logger: structlog.stdlib.BoundLogger, cache_key: str, **kwargs) -> None:
    """Log cache miss (WARNING level)."""
    logger.warning("cache_miss", cache_key=cache_key, **kwargs)


def log_connection_established(logger: structlog.stdlib.BoundLogger, server: str, **kwargs) -> None:
    """Log successful connection (INFO level)."""
    logger.info("connection_established", server=server, **kwargs)


def log_sync_complete(logger: structlog.stdlib.BoundLogger, items_synced: int, duration_ms: int, **kwargs) -> None:
    """Log sync completion (INFO level)."""
    logger.info("sync_complete", items_synced=items_synced, duration_ms=duration_ms, **kwargs)


def log_metrics_calculated(logger: structlog.stdlib.BoundLogger, metric_type: str, **kwargs) -> None:
    """Log metrics calculation (INFO level)."""
    logger.info("metrics_calculated", metric_type=metric_type, **kwargs)


def log_request(logger: structlog.stdlib.BoundLogger, method: str, url: str, **kwargs) -> None:
    """Log HTTP request details (DEBUG level)."""
    logger.debug("http_request", method=method, url=url, **kwargs)


def log_cache_operation(logger: structlog.stdlib.BoundLogger, operation: str, key: str, **kwargs) -> None:
    """Log cache operation (DEBUG level)."""
    logger.debug("cache_operation", operation=operation, key=key, **kwargs)
