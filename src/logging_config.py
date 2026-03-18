"""
Centralized logging configuration for Structural Design Platform.

This module provides a consistent logging setup across all modules,
with support for both console and file output, log rotation, and 
configurable log levels via environment variables.

Usage:
    from src.logging_config import get_logger
    
    logger = get_logger(__name__)
    logger.info("Analysis started")
    logger.debug("Detailed calculation: %s", value)
    logger.error("Failed to load file: %s", error)
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


# Default configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "[%(asctime)s] %(levelname)s [%(name)s] %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_FILE = "structural_design.log"
MAX_LOG_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3


def get_log_level() -> int:
    """Get log level from environment variable LOG_LEVEL."""
    level_name = os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_name, logging.INFO)


def setup_logging(
    log_file: Optional[str] = None,
    log_level: Optional[int] = None,
    console_output: bool = True,
    file_output: bool = True
) -> None:
    """
    Configure the root logger with console and/or file handlers.
    
    Args:
        log_file: Path to log file. Defaults to 'structural_design.log'.
        log_level: Logging level. Defaults to LOG_LEVEL env var or INFO.
        console_output: Whether to output to console (default: True).
        file_output: Whether to output to file (default: True).
    """
    if log_level is None:
        log_level = get_log_level()
    
    if log_file is None:
        log_file = DEFAULT_LOG_FILE
    
    # Get root logger for the package
    root_logger = logging.getLogger("src")
    root_logger.setLevel(log_level)
    
    # Avoid adding duplicate handlers
    if root_logger.handlers:
        return
    
    formatter = logging.Formatter(DEFAULT_LOG_FORMAT, DEFAULT_DATE_FORMAT)
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if file_output:
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=MAX_LOG_SIZE_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8"
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            # If we can't create the log file, just use console
            if console_output:
                root_logger.warning(f"Could not create log file '{log_file}': {e}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module name.
    
    This ensures logging is set up before returning the logger.
    
    Args:
        name: Module name, typically __name__.
        
    Returns:
        Configured Logger instance.
    """
    # Ensure logging is configured
    setup_logging()
    
    return logging.getLogger(name)


# For Streamlit apps, we might want to suppress file logging
def setup_streamlit_logging() -> None:
    """
    Configure logging for Streamlit apps (console only, no file output).
    
    Streamlit has its own logging, so we configure a simpler setup
    that doesn't interfere with it.
    """
    setup_logging(console_output=True, file_output=False)
