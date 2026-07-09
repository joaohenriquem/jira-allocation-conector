"""
UI Styles and Theme for Jira Allocation Connector.

Based on Efí Bank brand identity.
"""

import streamlit as st
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.data_models import AllocationStatus


# =============================================================================
# Color Palette - Efí Bank Design System (GMUD Reference)
# =============================================================================

# Primary color - Efí Blue (interactive elements, active states)
PRIMARY_COLOR = "rgb(24, 103, 192)"
PRIMARY_COLOR_HEX = "#1867C0"
PRIMARY_COLOR_DARK = "#1F5592"

# Secondary color - Efí Teal (accent, badges, highlights)
SECONDARY_COLOR = "#48A9A6"
SECONDARY_COLOR_DARK = "#018786"

# Brand color - Efí Orange (logo only)
BRAND_ORANGE = "#e85d1b"

# Background colors
BACKGROUND_LIGHT = "#ffffff"
BACKGROUND_DARK = "#121212"
BACKGROUND_SIDEBAR = "#F5F5F5"

# Dark tones
SECONDARY_BLACK = "#1e293b"
SECONDARY_DARK = "#334155"
SECONDARY_MEDIUM = "#424242"
SECONDARY_LIGHT = "#6B6B6B"
SECONDARY_GRAY = "#9CA3AF"

# Text colors
TEXT_PRIMARY = "rgba(0, 0, 0, 0.87)"
TEXT_SECONDARY = "rgba(0, 0, 0, 0.6)"
TEXT_LIGHT = "#FFFFFF"

# Border
BORDER_COLOR = "rgba(0, 0, 0, 0.12)"

# =============================================================================
# Status Colors
# =============================================================================

STATUS_COLORS = {
    "normal": "#4CAF50",        # Green (success)
    "warning": "#FB8C00",       # Orange (warning)
    "underutilized": "#FB8C00", # Orange
    "critical": "#B00020",      # Red (error)
    "overloaded": "#B00020",    # Red
}


# =============================================================================
# Theme Application
# =============================================================================

def apply_custom_theme() -> None:
    """
    Apply custom CSS theme based on Efí Bank Design System.
    Premium visual refinement with proper spacing, typography, and hierarchy.
    """
    custom_css = f"""
    <style>
        /* ═══════════════════════════════════════════════
           RESET & BASE
           ═══════════════════════════════════════════════ */
        
        .stMainBlockContainer,
        .block-container,
        [data-testid="stAppViewBlockContainer"] {{
            padding-top: 0.5rem !important;
            padding-left: 2.5rem !important;
            padding-right: 2.5rem !important;
            max-width: 100% !important;
            margin-left: 0 !important;
        }}
        
        header[data-testid="stHeader"] {{
            height: 0 !important;
            min-height: 0 !important;
            padding: 0 !important;
            background: transparent;
        }}
        
        /* Hide Streamlit chrome */
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"],
        .stDeployButton,
        [data-testid="stToolbar"],
        .stAppDeployButton,
        #MainMenu,
        footer {{
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            min-width: 0 !important;
        }}
        
        .stApp > header + div {{
            margin-left: 0 !important;
            padding-left: 0 !important;
        }}
        
        [data-testid="stAppViewContainer"] {{
            margin-left: 0 !important;
        }}
        
        .main .block-container {{
            padding-left: 2.5rem !important;
            margin-left: 0 !important;
        }}

        /* ═══════════════════════════════════════════════
           BACKGROUND & SURFACE
           ═══════════════════════════════════════════════ */
        
        .stApp {{
            background-color: {BACKGROUND_LIGHT};
        }}

        /* ═══════════════════════════════════════════════
           TYPOGRAPHY
           ═══════════════════════════════════════════════ */
        
        h1 {{
            color: {TEXT_PRIMARY};
            font-weight: 700;
            font-size: 1.75rem !important;
            letter-spacing: -0.02em;
        }}
        
        h2 {{
            color: {TEXT_PRIMARY};
            font-weight: 600;
            font-size: 1.25rem !important;
            letter-spacing: -0.01em;
        }}
        
        h3 {{
            color: {TEXT_SECONDARY};
            font-weight: 500;
            font-size: 1rem !important;
        }}
        
        p, span, label, div {{
            letter-spacing: 0.01em;
        }}
        
        a {{
            color: {PRIMARY_COLOR_HEX};
            text-decoration: none;
            transition: color 0.15s ease;
        }}
        
        a:hover {{
            color: {PRIMARY_COLOR_DARK};
        }}

        /* ═══════════════════════════════════════════════
           BUTTONS
           ═══════════════════════════════════════════════ */
        
        .stButton > button {{
            background-color: {PRIMARY_COLOR_HEX};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 0.5rem 1.25rem;
            font-weight: 500;
            font-size: 0.8125rem;
            transition: background-color 0.15s ease, transform 0.1s ease;
        }}
        
        .stButton > button:hover {{
            background-color: {PRIMARY_COLOR_DARK};
        }}
        
        .stButton > button:active {{
            transform: scale(0.98);
        }}
        
        .stButton > button[kind="secondary"] {{
            background-color: transparent;
            color: {TEXT_SECONDARY};
            border: 1px solid {BORDER_COLOR};
            border-radius: 6px;
        }}
        
        .stButton > button[kind="secondary"]:hover {{
            background-color: #f8f9fa;
            border-color: {TEXT_SECONDARY};
        }}
        
        .stButton > button[kind="tertiary"] {{
            background-color: transparent;
            color: {TEXT_SECONDARY};
            border: none;
            padding: 0.4rem 0.75rem;
            font-size: 0.8125rem;
        }}
        
        .stButton > button[kind="tertiary"]:hover {{
            color: {TEXT_PRIMARY};
            background-color: #f0f1f3;
        }}

        /* ═══════════════════════════════════════════════
           METRIC CARDS
           ═══════════════════════════════════════════════ */
        
        div[data-testid="metric-container"] {{
            background-color: white;
            border: 1px solid {BORDER_COLOR};
            border-radius: 8px;
            padding: 1.25rem 1rem;
        }}
        
        div[data-testid="metric-container"] label {{
            color: {TEXT_SECONDARY};
            font-size: 0.75rem;
            font-weight: 400;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
            color: {TEXT_PRIMARY};
            font-weight: 700;
            font-size: 1.5rem !important;
        }}

        /* ═══════════════════════════════════════════════
           TABS
           ═══════════════════════════════════════════════ */
        
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0;
            border-bottom: 1px solid {BORDER_COLOR};
        }}
        
        .stTabs [data-baseweb="tab"] {{
            color: {TEXT_SECONDARY};
            padding: 0.875rem 1.25rem;
            font-weight: 400;
            font-size: 0.875rem;
            transition: color 0.15s ease;
        }}
        
        .stTabs [data-baseweb="tab"]:hover {{
            color: {TEXT_PRIMARY};
        }}
        
        .stTabs [aria-selected="true"] {{
            color: {PRIMARY_COLOR_HEX};
            font-weight: 500;
            border-bottom: 2px solid {PRIMARY_COLOR_HEX};
            margin-bottom: -1px;
        }}

        /* ═══════════════════════════════════════════════
           FORM ELEMENTS
           ═══════════════════════════════════════════════ */
        
        /* Multiselect tags */
        span[data-baseweb="tag"] {{
            background-color: {PRIMARY_COLOR_HEX} !important;
            border-radius: 4px !important;
            font-size: 0.75rem !important;
        }}
        
        /* Select/Input focus */
        [data-baseweb="select"] div:focus-within,
        [data-baseweb="input"] div:focus-within {{
            border-color: {PRIMARY_COLOR_HEX} !important;
        }}

        /* ═══════════════════════════════════════════════
           EXPANDERS
           ═══════════════════════════════════════════════ */
        
        .streamlit-expanderHeader {{
            background-color: transparent;
            border-radius: 6px;
            color: {TEXT_PRIMARY};
            font-weight: 500;
            font-size: 0.875rem;
            padding: 0.5rem 0;
        }}
        
        .streamlit-expanderHeader:hover {{
            background-color: #f8f9fa;
        }}
        
        details[open] > summary {{
            border-bottom: 1px solid {BORDER_COLOR};
            padding-bottom: 0.75rem;
            margin-bottom: 0.75rem;
        }}

        /* ═══════════════════════════════════════════════
           ALERTS
           ═══════════════════════════════════════════════ */
        
        .stAlert {{
            border-radius: 8px;
        }}
        
        div[data-testid="stNotification"] {{
            border-radius: 8px;
        }}

        /* ═══════════════════════════════════════════════
           DATA ELEMENTS
           ═══════════════════════════════════════════════ */
        
        /* Divider */
        hr {{
            border-color: {BORDER_COLOR};
            margin: 2rem 0;
            opacity: 0.6;
        }}
        
        /* Caption */
        .stCaption {{
            color: {TEXT_SECONDARY};
            font-size: 0.75rem;
        }}
        
        /* Download button */
        .stDownloadButton > button {{
            background-color: white;
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_COLOR};
            border-radius: 6px;
            font-size: 0.8125rem;
        }}
        
        .stDownloadButton > button:hover {{
            background-color: #f8f9fa;
            border-color: {TEXT_SECONDARY};
        }}

        /* ═══════════════════════════════════════════════
           PROGRESS BAR
           ═══════════════════════════════════════════════ */
        
        .stProgress > div > div {{
            background-color: {PRIMARY_COLOR_HEX};
            border-radius: 4px;
        }}

        /* ═══════════════════════════════════════════════
           STATUS BADGES
           ═══════════════════════════════════════════════ */
        
        .status-normal {{
            color: {STATUS_COLORS["normal"]};
            background-color: {STATUS_COLORS["normal"]}10;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-weight: 500;
            font-size: 0.75rem;
            border: 1px solid {STATUS_COLORS["normal"]}30;
        }}
        
        .status-warning, .status-underutilized {{
            color: {STATUS_COLORS["warning"]};
            background-color: {STATUS_COLORS["warning"]}10;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-weight: 500;
            font-size: 0.75rem;
            border: 1px solid {STATUS_COLORS["warning"]}30;
        }}
        
        .status-critical, .status-overloaded {{
            color: {STATUS_COLORS["critical"]};
            background-color: {STATUS_COLORS["critical"]}10;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-weight: 500;
            font-size: 0.75rem;
            border: 1px solid {STATUS_COLORS["critical"]}30;
        }}

        /* ═══════════════════════════════════════════════
           DATAFRAMES
           ═══════════════════════════════════════════════ */
        
        [data-testid="stDataFrame"] {{
            border-radius: 8px;
            overflow: hidden;
        }}
    </style>
    """
    
    st.markdown(custom_css, unsafe_allow_html=True)


# =============================================================================
# Status Color Utility
# =============================================================================

def get_status_color(status: "AllocationStatus") -> str:
    """Get the color associated with an allocation status."""
    from src.models.data_models import AllocationStatus
    
    status_color_map = {
        AllocationStatus.NORMAL: STATUS_COLORS["normal"],
        AllocationStatus.OVERLOADED: STATUS_COLORS["overloaded"],
        AllocationStatus.UNDERUTILIZED: STATUS_COLORS["underutilized"],
    }
    
    return status_color_map.get(status, STATUS_COLORS["normal"])


def get_status_color_by_name(status_name: str) -> str:
    """Get the color associated with a status name string."""
    return STATUS_COLORS.get(status_name.lower(), STATUS_COLORS["normal"])
