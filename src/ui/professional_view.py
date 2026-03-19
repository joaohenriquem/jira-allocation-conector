"""
Professional View UI Components for Jira Allocation Connector.

This module contains Streamlit components for rendering the professional
allocation view, including selector, summary cards, breakdown charts,
and timeline visualization.
"""

from typing import List, Optional

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.models.data_models import (
    AllocationStatus,
    Professional,
    ProfessionalAllocation,
    ProjectAllocation,
    WeeklyAllocation,
)
from src.ui.styles import (
    PRIMARY_COLOR_HEX,
    STATUS_COLORS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    SECONDARY_GRAY,
    get_status_color,
)
from src.ui.charts import (
    CHART_LAYOUT,
    CHART_SECONDARY_COLORS,
)
from src.ui.components import (
    render_loading_skeleton,
    render_loading_card_skeleton,
)


# =============================================================================
# Professional Selector Component (Task 3.2)
# =============================================================================

def render_professional_selector(
    professionals: List[Professional]
) -> Optional[str]:
    """
    Render dropdown for professional selection.
    
    Displays a Streamlit selectbox with the list of available professionals,
    showing their display name and project count.
    
    Args:
        professionals: List of Professional objects to display
        
    Returns:
        Selected professional's account_id, or None if no selection
    """
    if not professionals:
        st.info("Nenhum profissional disponível. Verifique se há issues atribuídas nos projetos configurados.")
        return None
    
    # Create options with display name and project count
    options = {
        p.account_id: f"{p.display_name} ({p.project_count} projeto{'s' if p.project_count != 1 else ''})"
        for p in professionals
    }
    
    # Add empty option at the beginning
    account_ids = [""] + list(options.keys())
    
    def format_option(account_id: str) -> str:
        if not account_id:
            return "Selecione um profissional..."
        return options.get(account_id, account_id)
    
    selected = st.selectbox(
        "👤 Profissional",
        options=account_ids,
        format_func=format_option,
        key="professional_selector"
    )
    
    return selected if selected else None


# =============================================================================
# Professional Summary Component (Task 3.3)
# =============================================================================

def render_professional_summary(allocation: ProfessionalAllocation) -> None:
    """
    Render summary cards with professional allocation metrics.
    
    Displays cards showing:
    - Total allocation rate with status color indicator
    - Total story points
    - Total issues
    - Allocation status with visual indicator
    
    Args:
        allocation: ProfessionalAllocation object with calculated metrics
    """
    # Get status color and emoji
    status_color = get_status_color(allocation.status)
    status_emoji = {
        AllocationStatus.NORMAL: "✅",
        AllocationStatus.OVERLOADED: "🔴",
        AllocationStatus.UNDERUTILIZED: "🟡"
    }.get(allocation.status, "⚪")
    
    status_text = allocation.status.value
    
    # Header with professional name
    st.markdown(f"### 📊 Resumo de Alocação: {allocation.professional_name}")
    
    # Create 4 columns for metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Allocation rate card with color indicator
        rate_color = status_color
        st.markdown(
            f"""
            <div style="
                background-color: white;
                border-left: 4px solid {rate_color};
                border-radius: 8px;
                padding: 1rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            ">
                <div style="color: {TEXT_SECONDARY}; font-size: 0.875rem;">Taxa de Alocação</div>
                <div style="color: {TEXT_PRIMARY}; font-size: 1.5rem; font-weight: 600;">
                    {allocation.total_allocation_rate:.1f}%
                </div>
                <div style="color: {TEXT_SECONDARY}; font-size: 0.75rem;">
                    Capacidade: {allocation.capacity:.0f} SP
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            f"""
            <div style="
                background-color: white;
                border-left: 4px solid {PRIMARY_COLOR_HEX};
                border-radius: 8px;
                padding: 1rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            ">
                <div style="color: {TEXT_SECONDARY}; font-size: 0.875rem;">Esforço Total (horas)</div>
                <div style="color: {TEXT_PRIMARY}; font-size: 1.5rem; font-weight: 600;">
                    {allocation.total_story_points:.1f}h
                </div>
                <div style="color: {TEXT_SECONDARY}; font-size: 0.75rem;">
                    Baseado no T-Shirt Size
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown(
            f"""
            <div style="
                background-color: white;
                border-left: 4px solid {PRIMARY_COLOR_HEX};
                border-radius: 8px;
                padding: 1rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            ">
                <div style="color: {TEXT_SECONDARY}; font-size: 0.875rem;">Total de Issues</div>
                <div style="color: {TEXT_PRIMARY}; font-size: 1.5rem; font-weight: 600;">
                    {allocation.total_issues}
                </div>
                <div style="color: {TEXT_SECONDARY}; font-size: 0.75rem;">
                    Issues atribuídas
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col4:
        st.markdown(
            f"""
            <div style="
                background-color: white;
                border-left: 4px solid {status_color};
                border-radius: 8px;
                padding: 1rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            ">
                <div style="color: {TEXT_SECONDARY}; font-size: 0.875rem;">Status</div>
                <div style="color: {status_color}; font-size: 1.5rem; font-weight: 600;">
                    {status_emoji} {status_text}
                </div>
                <div style="color: {TEXT_SECONDARY}; font-size: 0.75rem;">
                    Classificação atual
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# =============================================================================
# Project Breakdown Chart Component (Task 3.4)
# =============================================================================

def render_project_breakdown_chart(breakdown: List[ProjectAllocation]) -> None:
    """
    Render distribution chart showing allocation by project.
    
    Displays a pie/donut chart showing how the professional's allocation
    is distributed across different projects.
    
    Args:
        breakdown: List of ProjectAllocation objects with per-project metrics
    """
    if not breakdown:
        st.info("Nenhum projeto encontrado para este profissional.")
        return
    
    st.markdown("### 📈 Distribuição por Projeto")
    
    # Prepare data for chart
    project_names = [p.project_name or p.project_key for p in breakdown]
    effort_hours = [p.story_points for p in breakdown]  # story_points now represents hours
    percentages = [p.allocation_percentage for p in breakdown]
    issue_counts = [p.issue_count for p in breakdown]
    
    # Create two columns: pie chart and table
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Create donut chart
        fig = go.Figure()
        
        fig.add_trace(go.Pie(
            labels=project_names,
            values=effort_hours,
            hole=0.4,
            marker_colors=CHART_SECONDARY_COLORS[:len(project_names)],
            textinfo='label+percent',
            textposition='outside',
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Esforço: %{value:.1f}h<br>"
                "Percentual: %{percent}<br>"
                "<extra></extra>"
            ),
        ))
        
        # Apply layout
        fig.update_layout(
            title="Distribuição de Esforço por Projeto (T-Shirt Size)",
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
        
        st.plotly_chart(fig, use_container_width=True, key="project_breakdown_pie")
    
    with col2:
        # Show breakdown table
        st.markdown("**Detalhamento**")
        for i, proj in enumerate(breakdown):
            color = CHART_SECONDARY_COLORS[i % len(CHART_SECONDARY_COLORS)]
            st.markdown(
                f"""
                <div style="
                    padding: 0.5rem;
                    margin-bottom: 0.5rem;
                    border-left: 3px solid {color};
                    background-color: #f9fafb;
                    border-radius: 4px;
                ">
                    <div style="font-weight: 600; color: {TEXT_PRIMARY};">
                        {proj.project_name or proj.project_key}
                    </div>
                    <div style="font-size: 0.875rem; color: {TEXT_SECONDARY};">
                        {proj.story_points:.1f}h • {proj.issue_count} issues • {proj.allocation_percentage:.1f}%
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


# =============================================================================
# Professional Timeline Chart Component (Task 3.5)
# =============================================================================

def render_professional_timeline(timeline: List[WeeklyAllocation]) -> None:
    """
    Render temporal evolution chart of professional allocation.
    
    Displays a line/area chart showing how the professional's allocation
    has evolved over time, with weekly data points.
    
    Args:
        timeline: List of WeeklyAllocation objects with weekly metrics
    """
    if not timeline:
        st.info("Nenhum dado de timeline disponível.")
        return
    
    st.markdown("### 📅 Evolução Temporal da Alocação")
    
    # Prepare data
    weeks = [f"{w.week_start.strftime('%d/%m')}" for w in timeline]
    allocation_rates = [w.allocation_rate for w in timeline]
    effort_hours = [w.total_story_points for w in timeline]  # story_points now represents hours
    
    # Create figure with secondary y-axis
    fig = go.Figure()
    
    # Add allocation rate line
    fig.add_trace(go.Scatter(
        x=weeks,
        y=allocation_rates,
        mode='lines+markers',
        name='Taxa de Alocação (%)',
        line=dict(
            color=PRIMARY_COLOR_HEX,
            width=3,
        ),
        marker=dict(
            size=8,
            color=PRIMARY_COLOR_HEX,
            line=dict(width=2, color='white'),
        ),
        fill='tozeroy',
        fillcolor="rgba(243, 112, 33, 0.1)",
        hovertemplate=(
            "<b>Semana %{x}</b><br>"
            "Taxa de Alocação: %{y:.1f}%<br>"
            "<extra></extra>"
        ),
    ))
    
    # Add threshold lines
    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color=STATUS_COLORS["critical"],
        annotation_text="100% (Sobrecarga)",
        annotation_position="right",
    )
    fig.add_hline(
        y=50,
        line_dash="dash",
        line_color=STATUS_COLORS["warning"],
        annotation_text="50% (Subutilizado)",
        annotation_position="right",
    )
    
    # Apply layout
    max_rate = max(allocation_rates) if allocation_rates else 100
    fig.update_layout(
        title="Evolução da Taxa de Alocação por Semana",
        xaxis_title="Semana",
        yaxis_title="Taxa de Alocação (%)",
        font_family=CHART_LAYOUT["font_family"],
        font_color=CHART_LAYOUT["font_color"],
        paper_bgcolor=CHART_LAYOUT["paper_bgcolor"],
        plot_bgcolor=CHART_LAYOUT["plot_bgcolor"],
        margin=CHART_LAYOUT["margin"],
        showlegend=False,
        xaxis=dict(
            gridcolor=SECONDARY_GRAY,
            gridwidth=0.5,
        ),
        yaxis=dict(
            gridcolor=SECONDARY_GRAY,
            gridwidth=0.5,
            range=[0, max(max_rate * 1.2, 120)],
        ),
        height=400,
    )
    
    st.plotly_chart(fig, use_container_width=True, key="professional_timeline")
    
    # Show effort breakdown per week in expander
    with st.expander("📊 Ver detalhes por semana"):
        for week in timeline:
            week_label = f"{week.week_start.strftime('%d/%m')} - {week.week_end.strftime('%d/%m')}"
            
            # Build project breakdown string
            if week.project_breakdown:
                breakdown_str = " | ".join(
                    f"{k}: {v:.1f} SP" for k, v in week.project_breakdown.items()
                )
            else:
                breakdown_str = "Sem alocação"
            
            st.markdown(
                f"""
                <div style="
                    padding: 0.5rem;
                    margin-bottom: 0.5rem;
                    border-left: 3px solid {PRIMARY_COLOR_HEX};
                    background-color: #f9fafb;
                    border-radius: 4px;
                ">
                    <div style="font-weight: 600; color: {TEXT_PRIMARY};">
                        Semana {week_label}
                    </div>
                    <div style="font-size: 0.875rem; color: {TEXT_SECONDARY};">
                        {week.total_story_points:.1f}h • {week.allocation_rate:.1f}% alocação
                    </div>
                    <div style="font-size: 0.75rem; color: {TEXT_SECONDARY};">
                        {breakdown_str}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


# =============================================================================
# Main Professional View Component (Task 3.6)
# =============================================================================

def render_professional_view_content(
    selected_professional_id: str,
    professionals: List[Professional],
    metrics_engine: "ProfessionalMetricsEngine"
) -> None:
    """
    Render the professional allocation view content (without selector).
    
    Args:
        selected_professional_id: Selected professional's account ID
        professionals: List of Professional objects
        metrics_engine: ProfessionalMetricsEngine instance for calculating metrics
    """
    from src.metrics.professional_metrics import ProfessionalMetricsEngine
    
    # Create placeholders for loading state
    loading_placeholder = st.empty()
    
    # Show loading skeleton while loading allocation data
    with loading_placeholder.container():
        render_loading_card_skeleton(4)
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            render_loading_skeleton(3, "200px", "Carregando dados de alocação...")
        with col2:
            render_loading_skeleton(3, "200px", "Carregando timeline...")
    
    # Load allocation data for selected professional (all projects)
    try:
        allocation = metrics_engine.calculate_cross_project_allocation(
            professional_id=selected_professional_id
        )
    except Exception as e:
        loading_placeholder.empty()
        st.error(f"Erro ao carregar dados de alocação: {str(e)}")
        return
    
    # Clear loading placeholder
    loading_placeholder.empty()
    
    # Render summary cards
    render_professional_summary(allocation)
    
    st.divider()
    
    # Create two columns for breakdown and timeline
    col1, col2 = st.columns(2)
    
    with col1:
        # Render project breakdown chart (shows which projects the professional is involved in)
        render_project_breakdown_chart(allocation.project_breakdown)
    
    with col2:
        # Create placeholder for timeline loading
        timeline_placeholder = st.empty()
        
        with timeline_placeholder.container():
            render_loading_skeleton(2, "150px", "Carregando timeline...")
        
        # Load and render timeline
        try:
            timeline = metrics_engine.get_professional_timeline(
                professional_id=selected_professional_id,
                weeks=8
            )
            timeline_placeholder.empty()
            render_professional_timeline(timeline)
        except Exception as e:
            timeline_placeholder.empty()
            st.warning(f"Não foi possível carregar o timeline: {str(e)}")
    
    st.divider()
    
    # Show detailed issues per project in expander
    with st.expander("📋 Ver issues por projeto"):
        for proj in allocation.project_breakdown:
            st.markdown(f"**{proj.project_name or proj.project_key}** ({proj.issue_count} issues)")
            
            if proj.issues:
                # Create a simple table with issue details
                issue_data = []
                for issue in proj.issues:
                    from src.models.data_models import get_tshirt_size_label
                    issue_data.append({
                        "Chave": issue.key,
                        "Resumo": issue.summary[:50] + "..." if len(issue.summary) > 50 else issue.summary,
                        "Status": issue.status,
                        "Tamanho": get_tshirt_size_label(issue.t_shirt_size),
                        "Criado": issue.created_date.strftime("%d/%m/%Y") if issue.created_date else "-",
                        "Início": issue.started_date.strftime("%d/%m/%Y") if issue.started_date else "-",
                        "Fim": issue.resolution_date.strftime("%d/%m/%Y") if issue.resolution_date else "-"
                    })
                
                if issue_data:
                    st.dataframe(
                        issue_data,
                        use_container_width=True,
                        hide_index=True
                    )
            else:
                st.caption("Nenhuma issue encontrada.")
            
            st.markdown("---")


def render_professional_view(
    professionals: List[Professional],
    metrics_engine: "ProfessionalMetricsEngine"
) -> None:
    """
    Render the complete professional allocation view tab.
    
    Flow:
    1. First, select a professional from the dropdown
    2. After selection, shows which projects the professional is involved in
    3. Displays allocation breakdown, timeline, and issue details per project
    
    Args:
        professionals: List of Professional objects for the selector
        metrics_engine: ProfessionalMetricsEngine instance for calculating metrics
    """
    from src.metrics.professional_metrics import ProfessionalMetricsEngine
    
    st.header("👤 Visão por Profissional")
    st.markdown(
        "Selecione um profissional para visualizar em quais projetos está alocado e sua distribuição de trabalho."
    )
    
    st.divider()
    
    # Render professional selector
    selected_professional_id = render_professional_selector(professionals)
    
    if not selected_professional_id:
        # Show message when no professional is selected
        st.info(
            "👆 Selecione um profissional no dropdown acima para visualizar "
            "em quais projetos está envolvido e sua alocação consolidada."
        )
        return
    
    st.divider()
    
    # Create placeholders for loading state
    loading_placeholder = st.empty()
    
    # Show loading skeleton while loading allocation data
    with loading_placeholder.container():
        render_loading_card_skeleton(4)
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            render_loading_skeleton(3, "200px", "Carregando dados de alocação...")
        with col2:
            render_loading_skeleton(3, "200px", "Carregando timeline...")
    
    # Load allocation data for selected professional (all projects)
    try:
        allocation = metrics_engine.calculate_cross_project_allocation(
            professional_id=selected_professional_id
        )
    except Exception as e:
        loading_placeholder.empty()
        st.error(f"Erro ao carregar dados de alocação: {str(e)}")
        return
    
    # Clear loading placeholder
    loading_placeholder.empty()
    
    # Render summary cards
    render_professional_summary(allocation)
    
    st.divider()
    
    # Create two columns for breakdown and timeline
    col1, col2 = st.columns(2)
    
    with col1:
        # Render project breakdown chart (shows which projects the professional is involved in)
        render_project_breakdown_chart(allocation.project_breakdown)
    
    with col2:
        # Create placeholder for timeline loading
        timeline_placeholder = st.empty()
        
        with timeline_placeholder.container():
            render_loading_skeleton(2, "150px", "Carregando timeline...")
        
        # Load and render timeline
        try:
            timeline = metrics_engine.get_professional_timeline(
                professional_id=selected_professional_id,
                weeks=8
            )
            timeline_placeholder.empty()
            render_professional_timeline(timeline)
        except Exception as e:
            timeline_placeholder.empty()
            st.warning(f"Não foi possível carregar o timeline: {str(e)}")
    
    st.divider()
    
    # Show detailed issues per project in expander
    with st.expander("📋 Ver issues por projeto"):
        for proj in allocation.project_breakdown:
            st.markdown(f"**{proj.project_name or proj.project_key}** ({proj.issue_count} issues)")
            
            if proj.issues:
                # Create a simple table with issue details
                issue_data = []
                for issue in proj.issues:
                    from src.models.data_models import get_tshirt_size_label
                    issue_data.append({
                        "Chave": issue.key,
                        "Resumo": issue.summary[:50] + "..." if len(issue.summary) > 50 else issue.summary,
                        "Status": issue.status,
                        "Tamanho": get_tshirt_size_label(issue.t_shirt_size),
                        "Criado": issue.created_date.strftime("%d/%m/%Y") if issue.created_date else "-",
                        "Início": issue.started_date.strftime("%d/%m/%Y") if issue.started_date else "-",
                        "Fim": issue.resolution_date.strftime("%d/%m/%Y") if issue.resolution_date else "-"
                    })
                
                if issue_data:
                    st.dataframe(
                        issue_data,
                        use_container_width=True,
                        hide_index=True
                    )
            else:
                st.caption("Nenhuma issue encontrada.")
            
            st.markdown("---")
