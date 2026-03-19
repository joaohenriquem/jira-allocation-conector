# UI Components Module

from src.ui.styles import (
    # Color palette constants
    PRIMARY_COLOR,
    PRIMARY_COLOR_HEX,
    BACKGROUND_LIGHT,
    BACKGROUND_DARK,
    SECONDARY_BLACK,
    SECONDARY_DARK,
    SECONDARY_MEDIUM,
    SECONDARY_LIGHT,
    SECONDARY_GRAY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    STATUS_COLORS,
    # Functions
    apply_custom_theme,
    get_status_color,
    get_status_color_by_name,
)

from src.ui.components import (
    # Connection status
    render_connection_status,
    # Metric cards
    render_metric_card,
    # Filters
    render_filters_sidebar,
    # Allocation metrics
    render_allocation_metrics,
    # Productivity metrics
    render_productivity_metrics,
    # CSV export
    export_to_csv,
    render_export_button,
    # Loading components
    render_loading_skeleton,
    render_loading_card_skeleton,
    render_loading_selector_skeleton,
)

from src.ui.charts import (
    # Chart functions
    render_allocation_chart,
    render_workload_pie_chart,
    render_trend_chart,
    render_velocity_chart,
    # Chart color constants
    CHART_PRIMARY,
    CHART_STATUS_COLORS,
    CHART_SECONDARY_COLORS,
    CHART_LAYOUT,
)

from src.ui.error_handlers import (
    # Error types
    ErrorType,
    # Error message functions
    render_error_message,
    render_warning_message,
    render_info_message,
    render_success_message,
    render_stale_data_warning,
    handle_exception,
)

from src.ui.professional_view import (
    # Professional view components
    render_professional_selector,
    render_professional_summary,
    render_project_breakdown_chart,
    render_professional_timeline,
    render_professional_view,
    render_professional_view_content,
)

__all__ = [
    # Color palette constants
    "PRIMARY_COLOR",
    "PRIMARY_COLOR_HEX",
    "BACKGROUND_LIGHT",
    "BACKGROUND_DARK",
    "SECONDARY_BLACK",
    "SECONDARY_DARK",
    "SECONDARY_MEDIUM",
    "SECONDARY_LIGHT",
    "SECONDARY_GRAY",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "STATUS_COLORS",
    # Style functions
    "apply_custom_theme",
    "get_status_color",
    "get_status_color_by_name",
    # Component functions
    "render_connection_status",
    "render_metric_card",
    "render_filters_sidebar",
    "render_allocation_metrics",
    "render_productivity_metrics",
    "export_to_csv",
    "render_export_button",
    # Loading components
    "render_loading_skeleton",
    "render_loading_card_skeleton",
    "render_loading_selector_skeleton",
    # Chart functions
    "render_allocation_chart",
    "render_workload_pie_chart",
    "render_trend_chart",
    "render_velocity_chart",
    # Chart color constants
    "CHART_PRIMARY",
    "CHART_STATUS_COLORS",
    "CHART_SECONDARY_COLORS",
    "CHART_LAYOUT",
    # Error handling
    "ErrorType",
    "render_error_message",
    "render_warning_message",
    "render_info_message",
    "render_success_message",
    "render_stale_data_warning",
    "handle_exception",
    # Professional view components
    "render_professional_selector",
    "render_professional_summary",
    "render_project_breakdown_chart",
    "render_professional_timeline",
    "render_professional_view",
    "render_professional_view_content",
]
