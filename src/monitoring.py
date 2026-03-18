"""
Error monitoring configuration for Structural Design Platform using Sentry.

This module provides centralized error tracking and performance monitoring
via Sentry SDK. Configuration is done through environment variables.

Features:
- Automatic exception capturing
- Performance monitoring with tracing
- Custom context tagging (user, project, etc.)
- Graceful degradation when Sentry is not configured

Setup:
1. Create a Sentry account at https://sentry.io
2. Create a new Python project
3. Copy the DSN and set it as environment variable:
   
   Windows (PowerShell):
       $env:SENTRY_DSN = "https://your-dsn@sentry.io/project-id"
   
   Linux/Mac:
       export SENTRY_DSN="https://your-dsn@sentry.io/project-id"

Usage:
    from src.monitoring import init_sentry, capture_exception, set_user_context
    
    # Initialize at app startup
    init_sentry()
    
    # Capture exceptions
    try:
        risky_operation()
    except Exception as e:
        capture_exception(e)
    
    # Set user context
    set_user_context(user_id="user123", username="john_doe")
"""

import os
from typing import Optional, Dict, Any
from functools import wraps

# Sentry SDK import with graceful fallback
try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    sentry_sdk = None

from .logging_config import get_logger

logger = get_logger(__name__)

# Environment variable for Sentry DSN
ENV_SENTRY_DSN = "SENTRY_DSN"
ENV_SENTRY_ENVIRONMENT = "SENTRY_ENVIRONMENT"
ENV_SENTRY_RELEASE = "SENTRY_RELEASE"

# Application metadata
APP_NAME = "structural-design-platform"
APP_VERSION = "1.0.0"


def init_sentry(
    dsn: Optional[str] = None,
    environment: Optional[str] = None,
    release: Optional[str] = None,
    sample_rate: float = 1.0,
    traces_sample_rate: float = 0.2,
    enable_logging_integration: bool = True
) -> bool:
    """
    Initialize Sentry SDK for error monitoring.
    
    Args:
        dsn: Sentry DSN. If not provided, reads from SENTRY_DSN env var.
        environment: Deployment environment (e.g., 'production', 'staging').
        release: Application release version.
        sample_rate: Error sampling rate (0.0 to 1.0).
        traces_sample_rate: Performance tracing sample rate.
        enable_logging_integration: Whether to capture log messages.
    
    Returns:
        True if Sentry was initialized successfully, False otherwise.
    """
    if not SENTRY_AVAILABLE:
        logger.warning("Sentry SDK not installed. Run: pip install sentry-sdk")
        return False
    
    # Get configuration from environment or parameters
    dsn = dsn or os.environ.get(ENV_SENTRY_DSN)
    environment = environment or os.environ.get(ENV_SENTRY_ENVIRONMENT, "development")
    release = release or os.environ.get(ENV_SENTRY_RELEASE, f"{APP_NAME}@{APP_VERSION}")
    
    if not dsn:
        logger.info("Sentry DSN not configured. Error monitoring disabled.")
        return False
    
    try:
        integrations = []
        
        if enable_logging_integration:
            # Capture WARNING and above as breadcrumbs, ERROR and above as events
            integrations.append(LoggingIntegration(
                level=20,       # INFO and above as breadcrumbs
                event_level=40  # ERROR and above as events
            ))
        
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            sample_rate=sample_rate,
            traces_sample_rate=traces_sample_rate,
            integrations=integrations,
            # Don't send PII by default
            send_default_pii=False,
            # Additional options
            attach_stacktrace=True,
            max_breadcrumbs=50,
        )
        
        logger.info("Sentry initialized successfully for environment: %s", environment)
        return True
        
    except Exception as e:
        logger.error("Failed to initialize Sentry: %s", e)
        return False


def capture_exception(
    exception: Optional[Exception] = None,
    **extra_context
) -> Optional[str]:
    """
    Capture and report an exception to Sentry.
    
    Args:
        exception: The exception to capture. If None, captures the current exception.
        **extra_context: Additional context to attach to the event.
    
    Returns:
        Sentry event ID if captured, None otherwise.
    """
    if not SENTRY_AVAILABLE or not sentry_sdk.Hub.current.client:
        return None
    
    with sentry_sdk.push_scope() as scope:
        for key, value in extra_context.items():
            scope.set_extra(key, value)
        
        return sentry_sdk.capture_exception(exception)


def capture_message(
    message: str,
    level: str = "info",
    **extra_context
) -> Optional[str]:
    """
    Capture and report a message to Sentry.
    
    Args:
        message: The message to capture.
        level: Message level ('debug', 'info', 'warning', 'error', 'fatal').
        **extra_context: Additional context to attach to the event.
    
    Returns:
        Sentry event ID if captured, None otherwise.
    """
    if not SENTRY_AVAILABLE or not sentry_sdk.Hub.current.client:
        return None
    
    with sentry_sdk.push_scope() as scope:
        for key, value in extra_context.items():
            scope.set_extra(key, value)
        
        return sentry_sdk.capture_message(message, level=level)


def set_user_context(
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    email: Optional[str] = None,
    **extra_data
) -> None:
    """
    Set the user context for subsequent error reports.
    
    Args:
        user_id: Unique user identifier.
        username: User's display name.
        email: User's email address.
        **extra_data: Additional user data.
    """
    if not SENTRY_AVAILABLE or not sentry_sdk.Hub.current.client:
        return
    
    user_data = {}
    if user_id:
        user_data["id"] = user_id
    if username:
        user_data["username"] = username
    if email:
        user_data["email"] = email
    user_data.update(extra_data)
    
    sentry_sdk.set_user(user_data)


def set_tag(key: str, value: str) -> None:
    """
    Set a tag for subsequent error reports.
    
    Tags are indexed and searchable in Sentry.
    
    Args:
        key: Tag name.
        value: Tag value.
    """
    if not SENTRY_AVAILABLE or not sentry_sdk.Hub.current.client:
        return
    
    sentry_sdk.set_tag(key, value)


def set_context(name: str, data: Dict[str, Any]) -> None:
    """
    Set a context block for subsequent error reports.
    
    Contexts provide additional structured data.
    
    Args:
        name: Context name (e.g., 'project', 'analysis').
        data: Context data as a dictionary.
    """
    if not SENTRY_AVAILABLE or not sentry_sdk.Hub.current.client:
        return
    
    sentry_sdk.set_context(name, data)


def add_breadcrumb(
    message: str,
    category: str = "default",
    level: str = "info",
    **data
) -> None:
    """
    Add a breadcrumb for debugging context.
    
    Breadcrumbs are trail of events leading to an error.
    
    Args:
        message: Breadcrumb message.
        category: Category (e.g., 'ui', 'http', 'query').
        level: Level ('debug', 'info', 'warning', 'error', 'critical').
        **data: Additional data to attach.
    """
    if not SENTRY_AVAILABLE or not sentry_sdk.Hub.current.client:
        return
    
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data
    )


def monitor_performance(operation_name: str):
    """
    Decorator to monitor function performance.
    
    Usage:
        @monitor_performance("load_cad_file")
        def load_cad(path):
            # ... expensive operation
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not SENTRY_AVAILABLE or not sentry_sdk.Hub.current.client:
                return func(*args, **kwargs)
            
            with sentry_sdk.start_transaction(op="function", name=operation_name):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def is_sentry_enabled() -> bool:
    """
    Check if Sentry is enabled and initialized.
    
    Returns:
        True if Sentry is active, False otherwise.
    """
    if not SENTRY_AVAILABLE:
        return False
    
    return sentry_sdk.Hub.current.client is not None


# --- Streamlit Integration ---

def init_sentry_for_streamlit() -> bool:
    """
    Initialize Sentry with settings optimized for Streamlit apps.
    
    Returns:
        True if initialized successfully, False otherwise.
    """
    return init_sentry(
        traces_sample_rate=0.1,  # Lower trace rate for web apps
        enable_logging_integration=True
    )


def set_streamlit_context(project_name: str = None, input_mode: str = None) -> None:
    """
    Set common context for Streamlit app errors.
    
    Args:
        project_name: Name of the current project.
        input_mode: Current input mode (Manual/CAD/BIM).
    """
    context = {}
    if project_name:
        context["project_name"] = project_name
    if input_mode:
        context["input_mode"] = input_mode
    
    if context:
        set_context("streamlit", context)
