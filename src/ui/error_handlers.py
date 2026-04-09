"""
Error Handlers for Jira Allocation Connector UI.

This module provides user-friendly error message rendering functions
for displaying errors, warnings, and informational messages in the
Streamlit dashboard.
"""

from enum import Enum
from typing import Optional

import streamlit as st

from src.ui.styles import STATUS_COLORS, TEXT_PRIMARY, TEXT_SECONDARY


class ErrorType(Enum):
    """Common error types for the application."""
    AUTH_ERROR = "auth_error"
    CONNECTION_ERROR = "connection_error"
    DATA_ERROR = "data_error"
    CONFIG_ERROR = "config_error"


# User-friendly error messages for each error type
ERROR_MESSAGES = {
    ErrorType.AUTH_ERROR: {
        "title": "🔐 Erro de Autenticação",
        "icon": "🔐",
        "color": STATUS_COLORS["critical"],
        "default_message": "Não foi possível autenticar com o Jira. Verifique suas credenciais.",
    },
    ErrorType.CONNECTION_ERROR: {
        "title": "🔌 Erro de Conexão",
        "icon": "🔌",
        "color": STATUS_COLORS["critical"],
        "default_message": "Não foi possível conectar ao servidor Jira. Verifique sua conexão de rede.",
    },
    ErrorType.DATA_ERROR: {
        "title": "📊 Erro de Dados",
        "icon": "📊",
        "color": STATUS_COLORS["warning"],
        "default_message": "Ocorreu um erro ao processar os dados. Alguns dados podem estar incompletos.",
    },
    ErrorType.CONFIG_ERROR: {
        "title": "⚙️ Erro de Configuração",
        "icon": "⚙️",
        "color": STATUS_COLORS["warning"],
        "default_message": "Há um problema com a configuração da aplicação.",
    },
}


def render_error_message(
    error_type: ErrorType,
    message: Optional[str] = None,
    details: Optional[str] = None
) -> None:
    """
    Render a user-friendly error message.
    
    Displays an error message with appropriate styling based on the error type.
    Technical details are hidden by default but can be expanded.
    
    Args:
        error_type: The type of error (AUTH_ERROR, CONNECTION_ERROR, etc.)
        message: Custom error message (uses default if not provided)
        details: Optional technical details (shown in expandable section)
        
    Example:
        >>> render_error_message(
        ...     ErrorType.AUTH_ERROR,
        ...     "Token expirado",
        ...     "HTTP 401: Unauthorized"
        ... )
    """
    error_config = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES[ErrorType.DATA_ERROR])
    
    display_message = message or error_config["default_message"]
    color = error_config["color"]
    title = error_config["title"]
    
    # Main error container
    st.markdown(
        f"""
        <div style="
            background-color: {color}15;
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
        ">
            <div style="
                color: {color};
                font-weight: 600;
                font-size: 1rem;
                margin-bottom: 0.5rem;
            ">{title}</div>
            <div style="
                color: {TEXT_PRIMARY};
                font-size: 0.9rem;
            ">{display_message}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Technical details in expandable section
    if details:
        with st.expander("🔍 Detalhes técnicos"):
            st.code(details, language=None)


def render_warning_message(message: str, details: Optional[str] = None) -> None:
    """
    Render a warning message.
    
    Displays a warning message with yellow/amber styling.
    
    Args:
        message: The warning message to display
        details: Optional additional details
        
    Example:
        >>> render_warning_message("Usando dados em cache (última atualização: 10 min atrás)")
    """
    color = STATUS_COLORS["warning"]
    
    st.markdown(
        f"""
        <div style="
            background-color: {color}15;
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
        ">
            <div style="
                color: {color};
                font-weight: 600;
                font-size: 1rem;
                margin-bottom: 0.5rem;
            ">⚠️ Aviso</div>
            <div style="
                color: {TEXT_PRIMARY};
                font-size: 0.9rem;
            ">{message}</div>
            {f'<div style="color: {TEXT_SECONDARY}; font-size: 0.8rem; margin-top: 0.5rem;">{details}</div>' if details else ''}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_info_message(message: str, details: Optional[str] = None) -> None:
    """
    Render an informational message.
    
    Displays an info message with blue styling.
    
    Args:
        message: The info message to display
        details: Optional additional details
        
    Example:
        >>> render_info_message("Sincronização em andamento...")
    """
    color = "#3b82f6"  # Blue color for info
    
    st.markdown(
        f"""
        <div style="
            background-color: {color}15;
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
        ">
            <div style="
                color: {color};
                font-weight: 600;
                font-size: 1rem;
                margin-bottom: 0.5rem;
            ">ℹ️ Informação</div>
            <div style="
                color: {TEXT_PRIMARY};
                font-size: 0.9rem;
            ">{message}</div>
            {f'<div style="color: {TEXT_SECONDARY}; font-size: 0.8rem; margin-top: 0.5rem;">{details}</div>' if details else ''}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_success_message(message: str, details: Optional[str] = None) -> None:
    """
    Render a success message.
    
    Displays a success message with green styling.
    
    Args:
        message: The success message to display
        details: Optional additional details
        
    Example:
        >>> render_success_message("Dados sincronizados com sucesso!")
    """
    color = STATUS_COLORS["normal"]
    
    st.markdown(
        f"""
        <div style="
            background-color: {color}15;
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
        ">
            <div style="
                color: {color};
                font-weight: 600;
                font-size: 1rem;
                margin-bottom: 0.5rem;
            ">✅ Sucesso</div>
            <div style="
                color: {TEXT_PRIMARY};
                font-size: 0.9rem;
            ">{message}</div>
            {f'<div style="color: {TEXT_SECONDARY}; font-size: 0.8rem; margin-top: 0.5rem;">{details}</div>' if details else ''}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_stale_data_warning() -> None:
    """
    Render a warning indicating that stale cached data is being displayed.
    
    This is used when a connection failure occurs and the application
    falls back to displaying cached data.
    """
    render_warning_message(
        "Exibindo dados em cache",
        "Não foi possível conectar ao Jira. Os dados exibidos podem estar desatualizados."
    )


def handle_exception(exception: Exception, show_details: bool = False) -> None:
    """
    Handle an exception and display a user-friendly error message.
    
    Determines the appropriate error type based on the exception and
    displays a friendly message.
    
    Args:
        exception: The exception that occurred
        show_details: Whether to show technical details
    """
    error_str = str(exception).lower()
    
    # Determine error type based on exception content
    if "auth" in error_str or "401" in error_str or "credential" in error_str:
        error_type = ErrorType.AUTH_ERROR
    elif "connection" in error_str or "timeout" in error_str or "network" in error_str:
        error_type = ErrorType.CONNECTION_ERROR
    elif "config" in error_str or "yaml" in error_str or "environment" in error_str:
        error_type = ErrorType.CONFIG_ERROR
    else:
        error_type = ErrorType.DATA_ERROR
    
    details = str(exception) if show_details else None
    render_error_message(error_type, details=details)
