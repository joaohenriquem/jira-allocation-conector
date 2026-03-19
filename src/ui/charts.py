"""
UI Charts for Jira Allocation Connector.

This module contains Plotly chart functions for visualizing
allocation metrics, workload distribution, trends, and velocity.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.data_models import AllocationMetrics, MetricTrend, Sprint

# Import color palette from styles
from src.ui.styles import (
    PRIMARY_COLOR,
    PRIMARY_COLOR_HEX,
    STATUS_COLORS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BACKGROUND_LIGHT,
    SECONDARY_GRAY,
)


# =============================================================================
# Chart Color Palette - Efí Bank Identity
# =============================================================================

# Primary chart color - Efí Orange (main brand color)
CHART_PRIMARY = PRIMARY_COLOR_HEX  # #F37021

# Status colors for allocation charts
CHART_STATUS_COLORS = {
    "normal": STATUS_COLORS["normal"],       # Efí Turquoise (good status)
    "overloaded": STATUS_COLORS["critical"], # Red
    "underutilized": STATUS_COLORS["warning"], # Amber
}

# Secondary colors for multi-series charts (Efí-inspired palette)
CHART_SECONDARY_COLORS = [
    PRIMARY_COLOR_HEX,  # Efí Orange #F37021
    "#D85F1A",          # Efí Dark Orange
    "#00A69C",          # Efí Turquoise
    "#008B83",          # Efí Dark Turquoise
    "#3b82f6",          # Blue
    "#8b5cf6",          # Purple
    "#10b981",          # Emerald
    "#ec4899",          # Pink
]

# Common chart layout settings
CHART_LAYOUT = {
    "font_family": "Inter, system-ui, sans-serif",
    "font_color": TEXT_PRIMARY,
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "margin": {"l": 40, "r": 40, "t": 40, "b": 40},
}


# =============================================================================
# Allocation Chart (Task 8.2)
# =============================================================================

def render_allocation_chart(
    data: List["AllocationMetrics"],
    group_by: str = "member"
) -> None:
    """
    Render a horizontal bar chart showing allocation rates.
    
    Displays allocation rate for each entity (team member or group) with
    color coding based on allocation status (normal, overloaded, underutilized).
    
    Args:
        data: List of AllocationMetrics objects containing allocation data
        group_by: Grouping label for the chart (e.g., "member", "team", "project")
        
    Example:
        >>> from src.models.data_models import AllocationMetrics, AllocationStatus
        >>> metrics = [
        ...     AllocationMetrics("1", "Alice", 85.0, 5, 17.0, AllocationStatus.NORMAL),
        ...     AllocationMetrics("2", "Bob", 120.0, 8, 24.0, AllocationStatus.OVERLOADED),
        ... ]
        >>> render_allocation_chart(metrics, group_by="member")
    """
    if not data:
        st.info("Nenhum dado de alocação disponível.")
        return
    
    # Prepare data for chart
    names = [m.entity_name for m in data]
    rates = [m.allocation_rate for m in data]
    colors = [CHART_STATUS_COLORS.get(m.status.value, CHART_STATUS_COLORS["normal"]) for m in data]
    
    # Create horizontal bar chart
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=names,
        x=rates,
        orientation='h',
        marker_color=colors,
        text=[f"{r:.1f}%" for r in rates],
        textposition='auto',
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Allocation: %{x:.1f}%<br>"
            "<extra></extra>"
        ),
    ))
    
    # Add threshold lines
    fig.add_vline(
        x=100, 
        line_dash="dash", 
        line_color=STATUS_COLORS["critical"],
        annotation_text="100% (Sobrecarga)",
        annotation_position="top",
    )
    fig.add_vline(
        x=50, 
        line_dash="dash", 
        line_color=STATUS_COLORS["warning"],
        annotation_text="50% (Subutilizado)",
        annotation_position="bottom",
    )
    
    # Apply layout
    fig.update_layout(
        title=f"Taxa de Alocação por {group_by.title()}",
        xaxis_title="Taxa de Alocação (%)",
        yaxis_title="",
        font_family=CHART_LAYOUT["font_family"],
        font_color=CHART_LAYOUT["font_color"],
        paper_bgcolor=CHART_LAYOUT["paper_bgcolor"],
        plot_bgcolor=CHART_LAYOUT["plot_bgcolor"],
        margin=CHART_LAYOUT["margin"],
        showlegend=False,
        xaxis=dict(
            gridcolor=SECONDARY_GRAY,
            gridwidth=0.5,
            range=[0, max(max(rates) * 1.1, 110)],
        ),
        yaxis=dict(
            gridcolor=SECONDARY_GRAY,
            gridwidth=0.5,
        ),
        height=max(300, len(data) * 50),
    )
    
    st.plotly_chart(fig, key="allocation_chart")


# =============================================================================
# Workload Pie Chart (Task 8.3)
# =============================================================================

def render_workload_pie_chart(distribution: dict[str, float]) -> None:
    """
    Render a pie chart showing workload distribution.
    
    Displays the percentage distribution of workload across team members
    or categories. The sum of all values should equal 100%.
    
    Args:
        distribution: Dictionary mapping entity names to their workload percentage
        
    Example:
        >>> distribution = {"Alice": 35.0, "Bob": 40.0, "Carol": 25.0}
        >>> render_workload_pie_chart(distribution)
    """
    if not distribution:
        st.info("Nenhum dado de distribuição disponível.")
        return
    
    names = list(distribution.keys())
    values = list(distribution.values())
    
    # Create pie chart with custom colors
    fig = go.Figure()
    
    fig.add_trace(go.Pie(
        labels=names,
        values=values,
        hole=0.4,  # Donut chart style
        marker_colors=CHART_SECONDARY_COLORS[:len(names)],
        textinfo='label+percent',
        textposition='outside',
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Workload: %{value:.1f}%<br>"
            "<extra></extra>"
        ),
    ))
    
    # Apply layout
    fig.update_layout(
        title="Distribuição por Tipo",
        font_family=CHART_LAYOUT["font_family"],
        font_color=CHART_LAYOUT["font_color"],
        paper_bgcolor=CHART_LAYOUT["paper_bgcolor"],
        plot_bgcolor=CHART_LAYOUT["plot_bgcolor"],
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
        ),
        height=400,
    )
    
    st.plotly_chart(fig, key="workload_pie")


# =============================================================================
# Combined Allocation and Type Distribution Chart
# =============================================================================

def render_combined_allocation_chart(
    allocation_data: List["AllocationMetrics"],
    type_distribution: dict[str, int],
    issues: List = None
) -> None:
    """
    Render a stacked bar chart showing allocation per member with type distribution.
    
    Args:
        allocation_data: List of AllocationMetrics objects
        type_distribution: Dictionary mapping issue types to counts (for legend)
        issues: List of issues to calculate per-member type distribution
    """
    if not allocation_data:
        st.info("Nenhum dado disponível para visualização.")
        return
    
    # Get all unique issue types
    all_types = set()
    member_type_effort = {}  # {member_id: {type: effort_hours}}
    
    if issues:
        for issue in issues:
            issue_type = issue.issue_type or "Outros"
            all_types.add(issue_type)
            
            member_id = issue.assignee_account_id
            if member_id:
                if member_id not in member_type_effort:
                    member_type_effort[member_id] = {}
                if issue_type not in member_type_effort[member_id]:
                    member_type_effort[member_id][issue_type] = 0
                member_type_effort[member_id][issue_type] += issue.story_points or 0  # story_points = hours
    
    all_types = sorted(list(all_types))
    
    # Create figure
    fig = go.Figure()
    
    # Prepare data for stacked bar chart
    members = [m.entity_name for m in allocation_data]
    member_ids = [m.entity_id for m in allocation_data]
    
    # Capacidade base para calcular percentual (horas por sprint)
    default_capacity = 24.0
    
    # Add a trace for each issue type
    for i, issue_type in enumerate(all_types):
        type_values = []
        for member_id in member_ids:
            effort = member_type_effort.get(member_id, {}).get(issue_type, 0)
            # Convert to allocation percentage
            allocation_pct = (effort / default_capacity) * 100 if default_capacity > 0 else 0
            type_values.append(allocation_pct)
        
        # Determine text position based on value size
        text_positions = ['outside' if v < 8 else 'inside' for v in type_values]
        
        fig.add_trace(go.Bar(
            name=issue_type,
            y=members,
            x=type_values,
            orientation='h',
            marker_color=CHART_SECONDARY_COLORS[i % len(CHART_SECONDARY_COLORS)],
            text=[f"{v:.0f}%" if v > 0 else "" for v in type_values],
            textposition=text_positions,
            textfont=dict(size=10),
            hovertemplate=f"<b>%{{y}}</b><br>{issue_type}: %{{x:.1f}}%<extra></extra>",
        ))
    
    # Add threshold lines
    fig.add_vline(
        x=100, 
        line_dash="dash", 
        line_color=STATUS_COLORS["critical"],
        line_width=2,
        annotation_text="100%",
        annotation_position="top"
    )
    fig.add_vline(
        x=50, 
        line_dash="dash", 
        line_color=STATUS_COLORS["warning"],
        line_width=1,
        annotation_text="50%",
        annotation_position="bottom"
    )
    
    # Calculate dynamic height
    num_members = len(allocation_data)
    chart_height = max(350, num_members * 50)
    
    # Get max allocation for x-axis range
    max_allocation = max(m.allocation_rate for m in allocation_data) if allocation_data else 100
    
    # Apply layout
    fig.update_layout(
        title="Alocação por Membro e Tipo de Card",
        barmode='stack',
        font_family=CHART_LAYOUT["font_family"],
        font_color=CHART_LAYOUT["font_color"],
        paper_bgcolor=CHART_LAYOUT["paper_bgcolor"],
        plot_bgcolor=CHART_LAYOUT["plot_bgcolor"],
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        height=chart_height,
        xaxis=dict(
            title="Taxa de Alocação (%)",
            gridcolor=SECONDARY_GRAY,
            gridwidth=0.5,
            range=[0, max(max_allocation * 1.15, 120)],
        ),
        yaxis=dict(
            gridcolor=SECONDARY_GRAY,
            gridwidth=0.5,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.35,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
            title=dict(
                text="Tipo de Card",
                font=dict(size=11)
            )
        )
    )
    
    st.plotly_chart(fig, use_container_width=True, key="combined_allocation_chart")


# =============================================================================
# Trend Chart (Task 8.4)
# =============================================================================

def render_trend_chart(
    data: List["MetricTrend"],
    metric_name: str
) -> None:
    """
    Render a line chart showing metric trends over time.
    
    Displays the evolution of a metric over time with date on x-axis
    and metric value on y-axis.
    
    Args:
        data: List of MetricTrend objects containing date and value pairs
        metric_name: Name of the metric being displayed (for title/labels)
        
    Example:
        >>> from src.models.data_models import MetricTrend
        >>> from datetime import date
        >>> trends = [
        ...     MetricTrend(date(2024, 1, 1), 85.0, "velocity"),
        ...     MetricTrend(date(2024, 1, 8), 92.0, "velocity"),
        ... ]
        >>> render_trend_chart(trends, "Velocity")
    """
    if not data:
        st.info(f"Nenhum dado de tendência disponível para {metric_name}.")
        return
    
    # Sort data by date
    sorted_data = sorted(data, key=lambda x: x.date)
    dates = [d.date for d in sorted_data]
    values = [d.value for d in sorted_data]
    
    # Create line chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=values,
        mode='lines+markers',
        name=metric_name,
        line=dict(
            color=CHART_PRIMARY,
            width=3,
        ),
        marker=dict(
            size=8,
            color=CHART_PRIMARY,
            line=dict(width=2, color='white'),
        ),
        fill='tozeroy',
        fillcolor="rgba(243, 112, 33, 0.1)",  # Efí Orange with transparency
        hovertemplate=(
            "<b>%{x}</b><br>"
            f"{metric_name}: %{{y:.1f}}<br>"
            "<extra></extra>"
        ),
    ))
    
    # Apply layout
    fig.update_layout(
        title=f"Tendência de {metric_name}",
        xaxis_title="Data",
        yaxis_title=metric_name,
        font_family=CHART_LAYOUT["font_family"],
        font_color=CHART_LAYOUT["font_color"],
        paper_bgcolor=CHART_LAYOUT["paper_bgcolor"],
        plot_bgcolor=CHART_LAYOUT["plot_bgcolor"],
        margin=CHART_LAYOUT["margin"],
        showlegend=False,
        xaxis=dict(
            gridcolor=SECONDARY_GRAY,
            gridwidth=0.5,
            tickformat="%b %d",
        ),
        yaxis=dict(
            gridcolor=SECONDARY_GRAY,
            gridwidth=0.5,
            rangemode="tozero",
        ),
        height=350,
    )
    
    st.plotly_chart(fig, key="trend_chart")


# =============================================================================
# Velocity Chart (Task 8.5)
# =============================================================================

def render_velocity_chart(
    sprints: List["Sprint"],
    velocities: List[float]
) -> None:
    """
    Render a bar chart showing velocity by sprint.
    
    Displays story points completed per sprint with sprint names on x-axis
    and velocity values on y-axis.
    
    Args:
        sprints: List of Sprint objects
        velocities: List of velocity values corresponding to each sprint
        
    Example:
        >>> from src.models.data_models import Sprint
        >>> sprints = [
        ...     Sprint(1, "Sprint 1", "closed", 100),
        ...     Sprint(2, "Sprint 2", "closed", 100),
        ... ]
        >>> velocities = [42.0, 38.0]
        >>> render_velocity_chart(sprints, velocities)
    """
    if not sprints or not velocities:
        st.info("Nenhum dado de velocity disponível.")
        return
    
    if len(sprints) != len(velocities):
        st.warning("Dados de sprint e velocity incompatíveis.")
        return
    
    sprint_names = [s.name for s in sprints]
    
    # Calculate average velocity for reference line
    avg_velocity = sum(velocities) / len(velocities) if velocities else 0
    
    # Create bar chart
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=sprint_names,
        y=velocities,
        marker_color=CHART_PRIMARY,
        text=[f"{v:.0f}" for v in velocities],
        textposition='outside',
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Velocity: %{y:.1f} pts<br>"
            "<extra></extra>"
        ),
    ))
    
    # Add average velocity line
    if avg_velocity > 0:
        fig.add_hline(
            y=avg_velocity,
            line_dash="dash",
            line_color=STATUS_COLORS["normal"],
            annotation_text=f"Média: {avg_velocity:.1f}",
            annotation_position="right",
        )
    
    # Apply layout
    fig.update_layout(
        title="Velocity por Sprint (T-Shirt Size)",
        xaxis_title="Sprint",
        yaxis_title="Esforço (horas)",
        font_family=CHART_LAYOUT["font_family"],
        font_color=CHART_LAYOUT["font_color"],
        paper_bgcolor=CHART_LAYOUT["paper_bgcolor"],
        plot_bgcolor=CHART_LAYOUT["plot_bgcolor"],
        margin=CHART_LAYOUT["margin"],
        showlegend=False,
        xaxis=dict(
            gridcolor=SECONDARY_GRAY,
            gridwidth=0.5,
            tickangle=-45 if len(sprints) > 5 else 0,
        ),
        yaxis=dict(
            gridcolor=SECONDARY_GRAY,
            gridwidth=0.5,
            rangemode="tozero",
        ),
        height=400,
    )
    
    st.plotly_chart(fig, key="velocity_chart")
