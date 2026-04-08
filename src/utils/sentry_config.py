"""
Sentry Configuration for Error Monitoring.

Initializes Sentry SDK for error tracking and performance monitoring.
"""

import os
import ssl
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Disable SSL verification globally for Sentry
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""

import sentry_sdk
from sentry_sdk.transport import HttpTransport
from sentry_sdk.integrations.logging import LoggingIntegration
import streamlit as st
import logging


class InsecureHttpTransport(HttpTransport):
    """Custom transport that bypasses SSL verification."""
    
    def _get_pool_options(self, ca_certs):
        options = super()._get_pool_options(ca_certs)
        options["cert_reqs"] = "CERT_NONE"
        options["ca_certs"] = None
        return options
    
    def _make_pool(self, *args, **kwargs):
        kwargs["cert_reqs"] = "CERT_NONE"
        kwargs["ca_certs"] = None
        return super()._make_pool(*args, **kwargs)


# Default DSN
DEFAULT_SENTRY_DSN = "https://182ea334024cc45892e9fad748980bb1@o4511031238852608.ingest.us.sentry.io/4511031242391552"


def init_sentry() -> bool:
    """
    Initialize Sentry SDK for error monitoring.
    
    Returns:
        True if Sentry was initialized, False otherwise.
    """
    # Try to get DSN from Streamlit secrets first, then environment, then default
    try:
        dsn = st.secrets.get("SENTRY_DSN", "")
    except Exception:
        dsn = os.getenv("SENTRY_DSN", "")
    
    # Use default DSN if not configured
    if not dsn:
        dsn = DEFAULT_SENTRY_DSN
    
    # Get environment
    try:
        environment = st.secrets.get("SENTRY_ENVIRONMENT", "production")
    except Exception:
        environment = os.getenv("SENTRY_ENVIRONMENT", "production")
    
    # Configure logging integration
    logging_integration = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR
    )
    
    try:
        # Try to set SSL cert bundle from certifi
        try:
            import certifi
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        except ImportError:
            pass
        
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            send_default_pii=True,
            debug=False,
            transport=InsecureHttpTransport,
            traces_sample_rate=1.0,
            profiles_sample_rate=0.1,
            integrations=[logging_integration],
            before_send=before_send,
        )
        print(f"[SENTRY] Inicializado com DSN={dsn[:50]}... | env={environment}")
        return True
    except Exception as e:
        print(f"[SENTRY] Falha ao inicializar: {e}")
        return False


def before_send(event, hint):
    """
    Filter events before sending to Sentry.
    Remove sensitive information.
    """
    # Remove sensitive headers if present
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        sensitive_headers = ["authorization", "cookie", "x-api-key", "api-token"]
        for header in sensitive_headers:
            if header in headers:
                headers[header] = "[FILTERED]"
    
    return event


def capture_exception(error: Exception, extra: dict = None):
    """
    Capture an exception and send to Sentry.
    
    Args:
        error: The exception to capture.
        extra: Additional context to include.
    """
    with sentry_sdk.push_scope() as scope:
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)
        sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", extra: dict = None):
    """
    Capture a message and send to Sentry.
    
    Args:
        message: The message to capture.
        level: Log level (info, warning, error).
        extra: Additional context to include.
    """
    with sentry_sdk.push_scope() as scope:
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)
        sentry_sdk.capture_message(message, level=level)


def set_user_context(email: str = None, user_id: str = None):
    """
    Set user context for Sentry events.
    
    Args:
        email: User email.
        user_id: User identifier.
    """
    user_data = {}
    
    if email:
        user_data["email"] = email
    
    if user_id:
        user_data["username"] = user_id
    
    if user_data:
        sentry_sdk.set_user(user_data)
