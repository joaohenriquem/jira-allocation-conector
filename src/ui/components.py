"""
UI Components for Jira Allocation Connector.

This module contains reusable Streamlit components for rendering
the dashboard UI including connection status, metric cards, filters,
and data export functionality.
"""

import csv
import io
from typing import List, Optional

import streamlit as st


from src.models.data_models import (
    AllocationMetrics,
    AllocationStatus,
    ConnectionStatus,
    DateRange,
    Filters,
    ProductivityMetrics,
    Project,
    Sprint,
)
from src.ui.styles import (
    PRIMARY_COLOR,
    STATUS_COLORS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    get_status_color,
    get_status_color_by_name,
)


# =============================================================================
# Loading Components
# =============================================================================

def render_loading_skeleton(
    num_items: int = 3,
    item_height: str = "60px",
    message: str = "Carregando..."
) -> None:
    """
    Render a loading skeleton placeholder with animated shimmer effect.
    
    Args:
        num_items: Number of skeleton items to display
        item_height: Height of each skeleton item
        message: Loading message to display
    """
    st.markdown(
        f"""
        <style>
        @keyframes shimmer {{
            0% {{ background-position: -200% 0; }}
            100% {{ background-position: 200% 0; }}
        }}
        .skeleton-container {{
            padding: 1rem 0;
        }}
        .skeleton-item {{
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 8px;
            height: {item_height};
            margin-bottom: 0.75rem;
        }}
        .skeleton-header {{
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 4px;
            height: 20px;
            width: 40%;
            margin-bottom: 1rem;
        }}
        .loading-message {{
            color: #6B7280;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }}
        .loading-spinner {{
            width: 16px;
            height: 16px;
            border: 2px solid #E5E7EB;
            border-top-color: #F97316;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        </style>
        <div class="skeleton-container">
            <div class="loading-message">
                <div class="loading-spinner"></div>
                {message}
            </div>
            <div class="skeleton-header"></div>
            {''.join([f'<div class="skeleton-item"></div>' for _ in range(num_items)])}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_loading_card_skeleton(num_cards: int = 4) -> None:
    """
    Render loading skeleton for metric cards.
    
    Args:
        num_cards: Number of card skeletons to display
    """
    cards_html = "".join([
        """
        <div class="card-skeleton">
            <div class="card-skeleton-title"></div>
            <div class="card-skeleton-value"></div>
        </div>
        """ for _ in range(num_cards)
    ])
    
    st.markdown(
        f"""
        <style>
        @keyframes card-shimmer {{
            0% {{ background-position: -200% 0; }}
            100% {{ background-position: 200% 0; }}
        }}
        .card-skeleton-container {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            margin: 1rem 0;
        }}
        .card-skeleton {{
            flex: 1;
            min-width: 150px;
            background: white;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }}
        .card-skeleton-title {{
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: card-shimmer 1.5s infinite;
            height: 14px;
            width: 60%;
            border-radius: 4px;
            margin-bottom: 0.75rem;
        }}
        .card-skeleton-value {{
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: card-shimmer 1.5s infinite;
            height: 28px;
            width: 80%;
            border-radius: 4px;
        }}
        </style>
        <div class="card-skeleton-container">{cards_html}</div>
        """,
        unsafe_allow_html=True
    )


def render_loading_selector_skeleton(message: str = "Carregando profissionais...") -> None:
    """
    Render loading skeleton for a selector/dropdown.
    
    Args:
        message: Loading message to display
    """
    st.markdown(
        f"""
        <style>
        @keyframes shimmer {{
            0% {{ background-position: -200% 0; }}
            100% {{ background-position: 200% 0; }}
        }}
        .selector-skeleton-container {{
            margin: 0.5rem 0;
        }}
        .selector-skeleton-label {{
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            height: 14px;
            width: 120px;
            border-radius: 4px;
            margin-bottom: 0.5rem;
        }}
        .selector-skeleton-input {{
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            height: 38px;
            width: 100%;
            border-radius: 4px;
            border: 1px solid #E5E7EB;
        }}
        .selector-loading-text {{
            color: #6B7280;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }}
        .mini-spinner {{
            width: 12px;
            height: 12px;
            border: 2px solid #E5E7EB;
            border-top-color: #F97316;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        </style>
        <div class="selector-skeleton-container">
            <div class="selector-skeleton-label"></div>
            <div class="selector-skeleton-input"></div>
            <div class="selector-loading-text">
                <div class="mini-spinner"></div>
                {message}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# =============================================================================
# Connection Status Component (Task 7.2)
# =============================================================================

def render_connection_status(status: ConnectionStatus) -> None:
    """
    Render connection status indicator in the header.
    
    Displays a colored indicator showing whether the application is
    connected to Jira, with additional info about staleness and errors.
    
    Args:
        status: ConnectionStatus object with connection details
    """
    if status.connected:
        if status.is_stale:
            # Connected but using stale cached data
            indicator_color = STATUS_COLORS["warning"]
            status_text = "⚠️ Conectado (dados em cache)"
            tooltip = "Usando dados em cache. Última verificação: " + \
                      status.last_checked.strftime("%H:%M:%S")
        else:
            # Fully connected
            indicator_color = STATUS_COLORS["normal"]
            status_text = "🟢 Conectado"
            tooltip = "Conectado ao Jira"
            if status.server_info:
                server_version = status.server_info.get("version", "N/A")
                tooltip += f" (v{server_version})"
    else:
        # Not connected
        indicator_color = STATUS_COLORS["critical"]
        status_text = "🔴 Desconectado"
        tooltip = status.error_message or "Não foi possível conectar ao Jira"
    
    # Render the status indicator
    st.markdown(
        f"""
        <div style="
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.75rem;
            background-color: {indicator_color}20;
            border-radius: 16px;
            border: 1px solid {indicator_color};
            font-size: 0.875rem;
            color: {indicator_color};
        " title="{tooltip}">
            {status_text}
        </div>
        """,
        unsafe_allow_html=True
    )


# =============================================================================
# Metric Card Component (Task 7.3)
# =============================================================================

def render_metric_card(
    title: str,
    value: any,
    status: str = "normal",
    tooltip: Optional[str] = None
) -> None:
    """
    Render a metric card with color based on status.
    
    Uses st.metric with custom styling based on the status parameter.
    
    Args:
        title: The metric title/label
        value: The metric value to display
        status: Status string (normal, warning, critical, overloaded, underutilized)
        tooltip: Optional tooltip text for additional context
    """
    color = get_status_color_by_name(status)
    
    # Format value for display
    display_value = "N/A" if value is None else str(value)
    
    # Create container with custom styling
    container_style = f"""
        <div style="
            background-color: white;
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 0.5rem;
        ">
            <div style="
                color: {TEXT_SECONDARY};
                font-size: 0.875rem;
                margin-bottom: 0.25rem;
            ">{title}</div>
            <div style="
                color: {TEXT_PRIMARY};
                font-size: 1.5rem;
                font-weight: 600;
            ">{display_value}</div>
            {f'<div style="color: {TEXT_SECONDARY}; font-size: 0.75rem; margin-top: 0.25rem;">{tooltip}</div>' if tooltip else ''}
        </div>
    """
    
    st.markdown(container_style, unsafe_allow_html=True)


# =============================================================================
# Filters Sidebar Component (Task 7.4)
# =============================================================================

def render_filters_sidebar(
    projects: List[Project],
    sprints: List[Sprint]
) -> Filters:
    """
    Render sidebar with project, sprint, and date range filters.
    
    Creates a sidebar with filter controls and returns the selected
    filter values as a Filters object.
    
    Args:
        projects: List of available projects
        sprints: List of available sprints (initial, will be updated dynamically)
        
    Returns:
        Filters object with selected filter values
    """
    # Force sidebar to be visible
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"][aria-expanded="false"] {
                display: block !important;
                min-width: 300px !important;
                margin-left: 0 !important;
            }
            [data-testid="stSidebar"] {
                min-width: 300px !important;
            }
            [data-testid="collapsedControl"] {
                display: none !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    with st.sidebar:
        st.header("🔍 Filtros")
        st.caption("Filtros aplicados à Visão por Projeto")
        
        st.divider()
        
        # Project filter
        st.subheader("Projeto")
        project_options = {p.key: f"{p.key} - {p.name}" for p in projects}
        
        if project_options:
            st.caption(f"{len(projects)} projetos disponíveis")
            selected_projects = st.multiselect(
                "Selecione os projetos",
                options=list(project_options.keys()),
                format_func=lambda x: project_options.get(x, x),
                key="filter_projects",
                placeholder="Selecione os projetos"
            )
        else:
            selected_projects = []
            st.warning("⚠️ Nenhum projeto disponível. Verifique a conexão com o Jira.")
        
        # Sprint filter - dynamic based on selected projects
        st.subheader("Sprint")
        
        # Get sprints for selected projects
        available_sprints = sprints
        if selected_projects and "connector" in st.session_state and st.session_state.connector:
            # Load sprints for selected projects
            from src.cache.cache_manager import CacheManager
            
            all_sprints = []
            for project_key in selected_projects:
                boards = st.session_state.connector.get_boards(project_key)
                for board in boards:
                    board_id = board.get("id")
                    if board_id:
                        cache_key = f"sprints_{board_id}"
                        cached = CacheManager.get_cached_data(cache_key)
                        if cached:
                            all_sprints.extend(cached)
                        else:
                            try:
                                board_sprints = st.session_state.connector.get_sprints(board_id)
                                CacheManager.set_cached_data(cache_key, board_sprints)
                                all_sprints.extend(board_sprints)
                            except:
                                pass
            
            # Remove duplicates
            seen_ids = set()
            unique_sprints = []
            for sprint in all_sprints:
                if sprint.jira_id not in seen_ids:
                    seen_ids.add(sprint.jira_id)
                    unique_sprints.append(sprint)
            
            # Sort sprints: active first, then future, then closed (most recent first)
            state_order = {"active": 0, "future": 1, "closed": 2}
            unique_sprints.sort(key=lambda s: (
                state_order.get(s.state, 3),
                -(s.start_date.timestamp() if s.start_date else 0)
            ))
            available_sprints = unique_sprints
        
        sprint_options = {s.jira_id: f"{s.name} ({s.state})" for s in available_sprints}
        
        if sprint_options:
            selected_sprint_ids = st.multiselect(
                "Selecione os sprints",
                options=list(sprint_options.keys()),
                format_func=lambda x: sprint_options.get(x, str(x)),
                key="filter_sprints",
                placeholder="Selecione os sprints"
            )
        else:
            selected_sprint_ids = []
            if selected_projects:
                st.info("Nenhum sprint encontrado para os projetos selecionados")
            else:
                st.info("Selecione um projeto para ver os sprints")
        
        # Issue type filter
        st.subheader("Tipo de Item")
        issue_type_options = ["Bug", "Task", "Sub-task", "Story", "Improvement", "Epic"]
        selected_issue_types = st.multiselect(
            "Selecione os tipos",
            options=issue_type_options,
            key="filter_issue_types",
            placeholder="Todos os tipos",
            help="Deixe vazio para mostrar todos os tipos"
        )
        
        # Clear filters button
        st.divider()
        if st.button("🗑️ Limpar Filtros", key="clear_filters_btn"):
            # Use query params to signal a reset
            st.query_params["reset_filters"] = "true"
            st.rerun()
        
        # Check if we need to reset filters
        if st.query_params.get("reset_filters") == "true":
            st.query_params.clear()
            # Return empty filters
            return Filters(
                project_keys=[],
                sprint_ids=[],
                date_range=None,
                assignees=[],
                issue_types=[]
            )
        
        # Help section
        st.divider()
        with st.expander("ℹ️ Ajuda"):
            st.markdown("""
            **Como usar os filtros:**
            1. Selecione um ou mais projetos
            2. Escolha os sprints desejados
            3. Opcionalmente, filtre por tipo de item
            4. Os dados serão atualizados automaticamente
            
            **Nota:** Estes filtros se aplicam apenas à aba "Visão por Projeto".
            A aba "Visão por Profissional" carrega todos os profissionais de todos os projetos.
            """)
    
    return Filters(
        project_keys=selected_projects,
        sprint_ids=selected_sprint_ids,
        date_range=None,
        assignees=[],
        issue_types=selected_issue_types
    )


# =============================================================================
# Allocation Metrics Component (Task 7.5)
# =============================================================================

def render_allocation_metrics(metrics: List[AllocationMetrics]) -> None:
    """
    Render allocation metrics cards and placeholder for charts.
    
    Displays allocation metrics for team members with visual indicators
    for their allocation status.
    
    Args:
        metrics: List of AllocationMetrics for team members
    """
    st.subheader("📊 Métricas de Alocação")
    
    if not metrics:
        st.info("Nenhuma métrica de alocação disponível")
        return
    
    # Summary metrics row
    total_members = len(metrics)
    overloaded_count = sum(1 for m in metrics if m.status == AllocationStatus.OVERLOADED)
    underutilized_count = sum(1 for m in metrics if m.status == AllocationStatus.UNDERUTILIZED)
    avg_allocation = sum(m.allocation_rate for m in metrics) / total_members if total_members > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Membros", total_members)
    
    with col2:
        st.metric(
            "Taxa Média de Alocação",
            f"{avg_allocation:.1f}%",
            delta=None
        )
    
    with col3:
        st.metric(
            "Sobrecarregados",
            overloaded_count,
            delta=f"{overloaded_count}" if overloaded_count > 0 else None,
            delta_color="inverse"
        )
    
    with col4:
        st.metric(
            "Subutilizados",
            underutilized_count,
            delta=f"{underutilized_count}" if underutilized_count > 0 else None,
            delta_color="inverse"
        )
    
    st.divider()
    
    # Individual member cards
    st.write("**Alocação por Membro**")
    
    # Create columns for member cards (3 per row)
    cols_per_row = 3
    for i in range(0, len(metrics), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < len(metrics):
                metric = metrics[i + j]
                with col:
                    status_str = metric.status.value
                    color = get_status_color(metric.status)
                    
                    # Status emoji
                    status_emoji = {
                        AllocationStatus.NORMAL: "✅",
                        AllocationStatus.OVERLOADED: "🔴",
                        AllocationStatus.UNDERUTILIZED: "🟡"
                    }.get(metric.status, "⚪")
                    
                    render_metric_card(
                        title=f"{status_emoji} {metric.entity_name}",
                        value=f"{metric.allocation_rate:.1f}%",
                        status=status_str,
                        tooltip=f"{metric.assigned_issues} issues | {metric.total_story_points:.1f}h esforço"
                    )
    
    # Placeholder for charts
    st.divider()
    st.write("**Gráficos de Alocação**")
    
    # Chart placeholder - will be implemented in charts.py
    chart_placeholder = st.empty()
    with chart_placeholder.container():
        st.info("📈 Gráfico de alocação será renderizado aqui (ver src/ui/charts.py)")


# =============================================================================
# Productivity Metrics Component (Task 7.6)
# =============================================================================

def render_productivity_metrics(metrics: ProductivityMetrics) -> None:
    """
    Render productivity metrics cards and placeholder for charts.
    
    Displays productivity metrics including throughput, lead time,
    cycle time, velocity, and completion rate.
    
    Args:
        metrics: ProductivityMetrics object with calculated values
    """
    st.subheader("⚡ Métricas de Produtividade")
    
    # Main metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Throughput",
            metrics.throughput,
            help="Número de issues concluídas"
        )
    
    with col2:
        lead_time_display = f"{metrics.lead_time_avg_hours:.1f}h" if metrics.lead_time_avg_hours else "N/A"
        st.metric(
            "Lead Time Médio",
            lead_time_display,
            help="Tempo médio desde criação até resolução"
        )
    
    with col3:
        cycle_time_display = f"{metrics.cycle_time_avg_hours:.1f}h" if metrics.cycle_time_avg_hours else "N/A"
        st.metric(
            "Cycle Time Médio",
            cycle_time_display,
            help="Tempo médio desde início até resolução"
        )
    
    with col4:
        velocity_display = f"{metrics.velocity:.1f}h" if metrics.velocity else "N/A"
        st.metric(
            "Velocity (horas)",
            velocity_display,
            help="Soma do esforço (horas) das issues concluídas, baseado no T-Shirt Size"
        )
    
    with col5:
        completion_display = f"{metrics.completion_rate:.1f}%" if metrics.completion_rate else "N/A"
        # Determine status based on completion rate
        if metrics.completion_rate:
            if metrics.completion_rate >= 80:
                status = "normal"
            elif metrics.completion_rate >= 60:
                status = "warning"
            else:
                status = "critical"
        else:
            status = "normal"
        
        st.metric(
            "Taxa de Conclusão",
            completion_display,
            help="Percentual de issues planejadas que foram concluídas"
        )
    
    # Detailed metrics cards
    st.divider()
    st.write("**Detalhamento**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Lead time status
        lead_status = "normal"
        if metrics.lead_time_avg_hours:
            if metrics.lead_time_avg_hours > 168:  # > 1 week
                lead_status = "critical"
            elif metrics.lead_time_avg_hours > 72:  # > 3 days
                lead_status = "warning"
        
        render_metric_card(
            title="Lead Time",
            value=lead_time_display,
            status=lead_status,
            tooltip="Tempo desde a criação da issue até sua resolução"
        )
    
    with col2:
        # Cycle time status
        cycle_status = "normal"
        if metrics.cycle_time_avg_hours:
            if metrics.cycle_time_avg_hours > 72:  # > 3 days
                cycle_status = "critical"
            elif metrics.cycle_time_avg_hours > 24:  # > 1 day
                cycle_status = "warning"
        
        render_metric_card(
            title="Cycle Time",
            value=cycle_time_display,
            status=cycle_status,
            tooltip="Tempo desde o início do trabalho até a resolução"
        )
    
    # Placeholder for charts
    st.divider()
    st.write("**Gráficos de Produtividade**")
    
    # Chart placeholder - will be implemented in charts.py
    chart_placeholder = st.empty()
    with chart_placeholder.container():
        st.info("📈 Gráficos de tendência e velocity serão renderizados aqui (ver src/ui/charts.py)")


# =============================================================================
# CSV Export Component (Task 7.7)
# =============================================================================

def export_to_csv(data: List[dict], filename: str) -> bytes:
    """
    Convert data to CSV format and return bytes for download.
    
    Creates a CSV file from a list of dictionaries and returns the
    bytes content suitable for use with st.download_button.
    
    Args:
        data: List of dictionaries to export
        filename: Suggested filename for the download
        
    Returns:
        CSV content as bytes
        
    Example:
        >>> data = [{"name": "John", "value": 100}, {"name": "Jane", "value": 200}]
        >>> csv_bytes = export_to_csv(data, "metrics.csv")
        >>> st.download_button("Download", csv_bytes, "metrics.csv", "text/csv")
    """
    if not data:
        return b""
    
    # Create CSV in memory
    output = io.StringIO()
    
    # Get all unique keys from all dictionaries
    fieldnames = []
    for row in data:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    
    # Get the CSV content as bytes
    csv_content = output.getvalue()
    output.close()
    
    return csv_content.encode('utf-8')


def render_export_button(
    data: List[dict],
    filename: str = "export.csv",
    button_label: str = "📥 Exportar CSV"
) -> None:
    """
    Render a download button for CSV export.
    
    Convenience function that combines export_to_csv with st.download_button.
    
    Args:
        data: List of dictionaries to export
        filename: Filename for the download
        button_label: Label for the download button
    """
    if not data:
        st.warning("Nenhum dado disponível para exportação")
        return
    
    csv_bytes = export_to_csv(data, filename)
    
    st.download_button(
        label=button_label,
        data=csv_bytes,
        file_name=filename,
        mime="text/csv"
    )
