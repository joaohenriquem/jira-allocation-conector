"""
UI Styles and Theme for Jira Allocation Connector.

Based on Efí Bank brand identity.
"""

import streamlit as st
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.data_models import AllocationStatus


# =============================================================================
# Color Palette - Efí Bank Identity
# =============================================================================

# Primary color - Efí Orange (main brand color)
PRIMARY_COLOR = "rgb(243, 112, 33)"
PRIMARY_COLOR_HEX = "#F37021"

# Secondary color - Efí Turquoise/Green
SECONDARY_COLOR = "#00A69C"
SECONDARY_COLOR_HEX = "#00A69C"

# Background colors
BACKGROUND_LIGHT = "#FFFFFF"
BACKGROUND_DARK = "#1A1A1A"
BACKGROUND_SIDEBAR = "#F5F5F5"

# Dark tones
SECONDARY_BLACK = "#1A1A1A"
SECONDARY_DARK = "#2D2D2D"
SECONDARY_MEDIUM = "#4A4A4A"
SECONDARY_LIGHT = "#6B6B6B"
SECONDARY_GRAY = "#9CA3AF"

# Text colors
TEXT_PRIMARY = "#1A1A1A"
TEXT_SECONDARY = "#6B7280"
TEXT_LIGHT = "#FFFFFF"

# =============================================================================
# Status Colors
# =============================================================================

STATUS_COLORS = {
    "normal": "#00A69C",       # Efí Turquoise (good)
    "warning": "#F59E0B",      # Amber (warning)
    "underutilized": "#F59E0B", # Amber
    "critical": "#EF4444",     # Red (critical)
    "overloaded": "#EF4444",   # Red
}


# =============================================================================
# Theme Application
# =============================================================================

def apply_custom_theme() -> None:
    """
    Apply custom CSS theme based on Efí Bank brand identity.
    """
    custom_css = f"""
    <style>
        /* Remove top padding/margin */
        .stMainBlockContainer,
        .block-container,
        [data-testid="stAppViewBlockContainer"] {{
            padding-top: 1rem !important;
        }}
        
        header[data-testid="stHeader"] {{
            height: 0 !important;
            min-height: 0 !important;
            padding: 0 !important;
        }}
        
        /* Hide sidebar completely */
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"],
        .st-emotion-cache-1oe5cao,
        .st-emotion-cache-eczf16 {{
            display: none !important;
            width: 0 !important;
            min-width: 0 !important;
        }}
        
        /* Remove left margin/padding caused by sidebar */
        .stMainBlockContainer,
        [data-testid="stAppViewBlockContainer"],
        .st-emotion-cache-1jicfl2,
        .block-container {{
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            max-width: 100% !important;
            margin-left: 0 !important;
        }}
        
        .stApp > header + div {{
            margin-left: 0 !important;
            padding-left: 0 !important;
        }}
        
        [data-testid="stAppViewContainer"] {{
            margin-left: 0 !important;
        }}
        
        /* Force main content to start from left */
        .main .block-container {{
            padding-left: 2rem !important;
            margin-left: 0 !important;
        }}
        
        /* Hide deploy button and Streamlit branding */
        .stDeployButton,
        [data-testid="stToolbar"],
        .stAppDeployButton,
        #MainMenu,
        footer {{
            display: none !important;
            visibility: hidden !important;
        }}
        
        header[data-testid="stHeader"] {{
            background: transparent;
        }}
        
        /* Main app background */
        .stApp {{
            background-color: {BACKGROUND_LIGHT};
        }}
        
        /* Primary button styling - Efí Orange */
        .stButton > button {{
            background-color: {PRIMARY_COLOR_HEX};
            color: white;
            border: none;
            border-radius: 25px;
            padding: 0.5rem 1.5rem;
            font-weight: 600;
            transition: all 0.3s ease;
        }}
        
        .stButton > button:hover {{
            background-color: #D85F1A;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(243, 112, 33, 0.3);
        }}
        
        .stButton > button:active {{
            transform: translateY(0);
        }}
        
        /* Secondary button (outline style) */
        .stButton > button[kind="secondary"] {{
            background-color: transparent;
            color: {PRIMARY_COLOR_HEX};
            border: 2px solid {PRIMARY_COLOR_HEX};
        }}
        
        .stButton > button[kind="secondary"]:hover {{
            background-color: {PRIMARY_COLOR_HEX}10;
        }}
        
        /* Metric card styling */
        div[data-testid="metric-container"] {{
            background-color: white;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            padding: 1rem;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        }}
        
        div[data-testid="metric-container"] label {{
            color: {TEXT_SECONDARY};
            font-size: 0.875rem;
        }}
        
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
            color: {TEXT_PRIMARY};
            font-weight: 700;
        }}
        
        /* Sidebar styling */
        section[data-testid="stSidebar"] {{
            background-color: {BACKGROUND_SIDEBAR};
            border-right: 1px solid #E5E7EB;
        }}
        
        section[data-testid="stSidebar"] .stSelectbox label,
        section[data-testid="stSidebar"] .stMultiSelect label {{
            color: {TEXT_PRIMARY};
            font-weight: 600;
        }}
        
        /* Header styling */
        h1 {{
            color: {TEXT_PRIMARY};
            font-weight: 700;
        }}
        
        h2 {{
            color: {TEXT_PRIMARY};
            font-weight: 600;
        }}
        
        h3 {{
            color: {TEXT_SECONDARY};
            font-weight: 600;
        }}
        
        /* Link styling */
        a {{
            color: {PRIMARY_COLOR_HEX};
            text-decoration: none;
        }}
        
        a:hover {{
            color: #D85F1A;
            text-decoration: underline;
        }}
        
        /* Status indicator classes */
        .status-normal {{
            color: {STATUS_COLORS["normal"]};
            background-color: {STATUS_COLORS["normal"]}15;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.875rem;
        }}
        
        .status-warning, .status-underutilized {{
            color: {STATUS_COLORS["warning"]};
            background-color: {STATUS_COLORS["warning"]}15;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.875rem;
        }}
        
        .status-critical, .status-overloaded {{
            color: {STATUS_COLORS["critical"]};
            background-color: {STATUS_COLORS["critical"]}15;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.875rem;
        }}
        
        /* Multiselect tag styling - Efí Orange */
        span[data-baseweb="tag"] {{
            background-color: {PRIMARY_COLOR_HEX} !important;
            border-radius: 20px !important;
        }}
        
        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0;
            border-bottom: 2px solid #E5E7EB;
        }}
        
        .stTabs [data-baseweb="tab"] {{
            color: {TEXT_SECONDARY};
            padding: 0.75rem 1.5rem;
            font-weight: 500;
        }}
        
        .stTabs [aria-selected="true"] {{
            color: {PRIMARY_COLOR_HEX};
            border-bottom: 3px solid {PRIMARY_COLOR_HEX};
            margin-bottom: -2px;
        }}
        
        /* Expander styling */
        .streamlit-expanderHeader {{
            background-color: #F9FAFB;
            border-radius: 8px;
            color: {TEXT_PRIMARY};
            font-weight: 500;
        }}
        
        .streamlit-expanderHeader:hover {{
            background-color: #F3F4F6;
        }}
        
        /* Info/Success/Warning boxes */
        .stAlert {{
            border-radius: 12px;
            border: none;
        }}
        
        div[data-testid="stNotification"] {{
            border-radius: 12px;
        }}
        
        /* Progress bar - Efí Orange */
        .stProgress > div > div {{
            background-color: {PRIMARY_COLOR_HEX};
        }}
        
        /* Divider */
        hr {{
            border-color: #E5E7EB;
            margin: 1.5rem 0;
        }}
        
        /* Caption text */
        .stCaption {{
            color: {TEXT_SECONDARY};
        }}
        
        /* Download button */
        .stDownloadButton > button {{
            background-color: {SECONDARY_COLOR};
            color: white;
            border: none;
            border-radius: 25px;
        }}
        
        .stDownloadButton > button:hover {{
            background-color: #008B83;
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
