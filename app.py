"""
Jira Allocation Connector - Streamlit Entry Point

Dashboard interativo para visualização de métricas de alocação e produtividade
de times de desenvolvimento integrado com Jira.
"""

import streamlit as st
from datetime import date, datetime, timedelta
from typing import List, Optional

# Page configuration - must be first Streamlit command
st.set_page_config(
    page_title="Efí - Acompanhamento Jira",
    page_icon="https://sejaefi.com.br/images/favicon/favicon-32x32.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Application imports
from src.config.config_loader import ConfigLoader
from src.connector.jira_connector import JiraConnector
from src.metrics.metrics_engine import MetricsEngine
from src.cache.cache_manager import CacheManager
from src.cache.cached_data import (
    get_all_projects_cached,
    get_all_professionals_cached,
    clear_all_caches,
    clear_professionals_cache,
)
from src.ai.assistant import get_ai_assistant
from src.ui.styles import apply_custom_theme
from src.ui.components import (
    render_connection_status,
    render_filters_sidebar,
    render_allocation_metrics,
    render_productivity_metrics,
    render_metric_card,
    export_to_csv,
    render_export_button,
)
from src.ui.charts import (
    render_allocation_chart,
    render_workload_pie_chart,
    render_trend_chart,
    render_velocity_chart,
    render_combined_allocation_chart,
)
from src.ui.professional_view import render_professional_view, render_professional_view_content
from src.ui.legacy_view import render_legacy_view
from src.metrics.professional_metrics import ProfessionalMetricsEngine
from src.models.data_models import (
    AllocationMetrics,
    AllocationStatus,
    AppConfig,
    ConnectionStatus,
    DateRange,
    Filters,
    Issue,
    JiraConfig,
    MetricTrend,
    ProductivityMetrics,
    Project,
    Sprint,
)

# Application version
APP_VERSION = "1.0.0"


# =============================================================================
# Access Control
# =============================================================================

def check_access() -> bool:
    """
    Check if user has access to the application.
    Returns True if authenticated, False otherwise.
    """
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if st.session_state.authenticated:
        return True
    
    # Show login dialog
    st.markdown(
        """
        <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 2rem;
            background: linear-gradient(135deg, #1A1A1A 0%, #2D2D2D 100%);
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Acesso ao Sistema")
        st.markdown("Digite seu email corporativo para continuar.")
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="seu.email@empresa.com.br")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            
            if submitted:
                if email:
                    email_lower = email.lower().strip()
                    if email_lower.endswith("@sejaefi.com.br") or email_lower.endswith("@gerencianet.com.br"):
                        st.session_state.authenticated = True
                        st.session_state.user_email = email_lower
                        st.rerun()
                    else:
                        st.error("Email não autorizado.")
                else:
                    st.warning("Por favor, digite seu email.")
    
    return False


# =============================================================================
# Session State Initialization (Task 9.1)
# =============================================================================

def init_session_state():
    """Initialize session state variables."""
    # Connection state
    if "connected" not in st.session_state:
        st.session_state.connected = False
    
    if "connection_status" not in st.session_state:
        st.session_state.connection_status = ConnectionStatus(
            connected=False,
            error_message="Não conectado ao Jira"
        )
    
    # AI Assistant toggle state
    if "ai_enabled" not in st.session_state:
        st.session_state.ai_enabled = False
    
    # Filter selections
    if "selected_projects" not in st.session_state:
        st.session_state.selected_projects = []
    
    if "selected_sprints" not in st.session_state:
        st.session_state.selected_sprints = []
    
    # Filters applied flag
    if "filters_applied" not in st.session_state:
        st.session_state.filters_applied = False
    
    # Demo mode flag
    if "demo_mode" not in st.session_state:
        st.session_state.demo_mode = True
    
    # Expanded metrics state for drill-down
    if "expanded_metrics" not in st.session_state:
        st.session_state.expanded_metrics = {}
    
    # Config loaded flag
    if "config" not in st.session_state:
        st.session_state.config = None
    
    # Connector instance
    if "connector" not in st.session_state:
        st.session_state.connector = None
    
    # Metrics engine instance
    if "metrics_engine" not in st.session_state:
        st.session_state.metrics_engine = None


# =============================================================================
# Configuration Loading (Task 9.1)
# =============================================================================

def load_configuration() -> Optional[AppConfig]:
    """
    Load application configuration from YAML and environment variables.
    
    Returns:
        AppConfig if successful, None if configuration fails.
    """
    try:
        config_loader = ConfigLoader("config.yaml")
        config = config_loader.load()
        return config
    except FileNotFoundError as e:
        st.warning(f"⚠️ Arquivo de configuração não encontrado: {e}")
        return None
    except ValueError as e:
        st.error(f"❌ Erro na configuração: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Erro ao carregar configuração: {e}")
        return None


def initialize_jira_connector(config: AppConfig) -> Optional[JiraConnector]:
    """
    Initialize Jira connector with graceful handling if credentials not set.
    
    Args:
        config: Application configuration with Jira credentials.
        
    Returns:
        JiraConnector if successful, None if initialization fails.
    """
    try:
        connector = JiraConnector(config.jira)
        return connector
    except ValueError as e:
        # Credentials not configured - this is expected in demo mode
        return None
    except Exception as e:
        st.error(f"❌ Erro ao inicializar conector Jira: {e}")
        return None


def test_jira_connection(connector: JiraConnector) -> ConnectionStatus:
    """
    Test connection to Jira and return status.
    
    Args:
        connector: Initialized JiraConnector.
        
    Returns:
        ConnectionStatus with connection result.
    """
    try:
        status = connector.test_connection()
        return status
    except Exception as e:
        return ConnectionStatus(
            connected=False,
            error_message=f"Erro ao testar conexão: {e}"
        )


# =============================================================================
# Data Loading Functions
# =============================================================================

def load_projects(connector: Optional[JiraConnector], config: Optional[AppConfig]) -> List[Project]:
    """Load projects from Jira."""
    if connector:
        cache_key = "projects"
        cached = CacheManager.get_cached_data(cache_key)
        if cached:
            return cached
        
        try:
            # If config has specific projects, use them; otherwise fetch all
            project_keys = config.projects if config and config.projects else []
            projects = connector.get_projects(project_keys)
            ttl = config.cache_ttl_seconds if config else 900
            CacheManager.set_cached_data(cache_key, projects, ttl)
            return projects
        except Exception as e:
            st.warning(f"⚠️ Erro ao carregar projetos: {e}")
    
    return []


def load_sprints_for_project(connector: Optional[JiraConnector], project_key: Optional[str] = None) -> List[Sprint]:
    """Load sprints from Jira for a specific project."""
    if not connector:
        return []
    
    # Get boards for the project
    boards = connector.get_boards(project_key)
    if not boards:
        return []
    
    all_sprints = []
    for board in boards:
        board_id = board.get("id")
        if not board_id:
            continue
            
        cache_key = f"sprints_{board_id}"
        cached = CacheManager.get_cached_data(cache_key)
        if cached:
            all_sprints.extend(cached)
            continue
        
        try:
            sprints = connector.get_sprints(board_id)
            CacheManager.set_cached_data(cache_key, sprints)
            all_sprints.extend(sprints)
        except Exception as e:
            # Log but continue with other boards
            pass
    
    # Remove duplicates by sprint id
    seen_ids = set()
    unique_sprints = []
    for sprint in all_sprints:
        if sprint.jira_id not in seen_ids:
            seen_ids.add(sprint.jira_id)
            unique_sprints.append(sprint)
    
    return unique_sprints


def load_sprints(connector: Optional[JiraConnector], board_id: Optional[int] = None) -> List[Sprint]:
    """Load sprints from Jira (legacy - use load_sprints_for_project instead)."""
    if connector:
        # If no board_id provided, try to get the first available board
        if board_id is None:
            boards = connector.get_boards()
            if boards:
                board_id = boards[0]["id"]
            else:
                return []
        
        cache_key = f"sprints_{board_id}"
        cached = CacheManager.get_cached_data(cache_key)
        if cached:
            return cached
        
        try:
            sprints = connector.get_sprints(board_id)
            CacheManager.set_cached_data(cache_key, sprints)
            return sprints
        except Exception as e:
            pass
    
    return []


def load_issues(connector: Optional[JiraConnector], filters: Filters) -> List[Issue]:
    """Load issues from Jira."""
    if not connector:
        return []
    
    # If no project selected, don't load issues (too many)
    if not filters.project_keys:
        return []
    
    # Build JQL from filters
    jql_parts = []
    
    # Project filter
    projects_str = ", ".join(filters.project_keys)
    jql_parts.append(f"project IN ({projects_str})")
    
    # Sprint filter - sort IDs for consistent cache key
    if filters.sprint_ids:
        sorted_sprint_ids = sorted(filters.sprint_ids)
        sprint_ids_str = ", ".join(str(sid) for sid in sorted_sprint_ids)
        jql_parts.append(f"sprint IN ({sprint_ids_str})")
    
    # Date range filter
    if filters.date_range:
        if filters.date_range.start:
            start_str = filters.date_range.start.strftime("%Y-%m-%d")
            jql_parts.append(f"created >= '{start_str}'")
        if filters.date_range.end:
            end_str = filters.date_range.end.strftime("%Y-%m-%d")
            jql_parts.append(f"created <= '{end_str}'")
    
    jql = " AND ".join(jql_parts)
    cache_key = f"issues_{hash(jql)}"
    
    cached = CacheManager.get_cached_data(cache_key)
    if cached:
        return cached
    
    try:
        fields = ["summary", "status", "assignee", "issuetype", "created",
                 "resolutiondate", "labels", "components", 
                 "customfield_10370", "customfield_10016", "customfield_10026",
                 "customfield_11891",
                 "statuscategorychangedate"]
        result = connector.get_issues(jql, fields)
        CacheManager.set_cached_data(cache_key, result.issues)
        return result.issues
    except Exception as e:
        st.warning(f"⚠️ Erro ao carregar issues: {e}")
        return []


# =============================================================================
# Metrics Calculation Functions
# =============================================================================

def calculate_allocation_metrics(
    issues: List[Issue],
    filters: Filters
) -> List[AllocationMetrics]:
    """
    Calculate allocation metrics from issues.
    
    Args:
        issues: List of issues to analyze.
        filters: Current filter settings.
        
    Returns:
        List of AllocationMetrics for each team member.
    """
    if not issues:
        return []
    
    # Group issues by assignee
    assignee_issues: dict[str, List[Issue]] = {}
    for issue in issues:
        if issue.assignee_account_id:
            if issue.assignee_account_id not in assignee_issues:
                assignee_issues[issue.assignee_account_id] = []
            assignee_issues[issue.assignee_account_id].append(issue)
    
    metrics = []
    # Capacidade: 4 dias/semana × 6 horas/dia = 24 horas por sprint
    # Assumindo 1 Story Point = 1 hora de trabalho
    default_capacity = 24.0
    
    for assignee_id, member_issues in assignee_issues.items():
        # Get assignee name
        assignee_name = assignee_id
        for issue in member_issues:
            if issue.assignee_name:
                assignee_name = issue.assignee_name
                break
        
        # Calculate story points
        total_sp = sum(issue.story_points or 0.0 for issue in member_issues)
        
        # Calculate allocation rate
        allocation_rate = (total_sp / default_capacity) * 100 if default_capacity > 0 else 0
        
        # Classify status
        if allocation_rate > 100:
            status = AllocationStatus.OVERLOADED
        elif allocation_rate < 50:
            status = AllocationStatus.UNDERUTILIZED
        else:
            status = AllocationStatus.NORMAL
        
        metrics.append(AllocationMetrics(
            entity_id=assignee_id,
            entity_name=assignee_name,
            allocation_rate=allocation_rate,
            assigned_issues=len(member_issues),
            total_story_points=total_sp,
            status=status
        ))
    
    # Sort by allocation rate (highest first - most overloaded first)
    metrics.sort(key=lambda m: m.allocation_rate, reverse=True)
    
    return metrics


def calculate_productivity_metrics(issues: List[Issue]) -> ProductivityMetrics:
    """
    Calculate productivity metrics from issues.
    
    Args:
        issues: List of issues to analyze.
        
    Returns:
        ProductivityMetrics with calculated values.
    """
    if not issues:
        return ProductivityMetrics(throughput=0)
    
    # Throughput: count of done issues
    done_issues = [i for i in issues if i.status_category == "Done"]
    throughput = len(done_issues)
    
    # Lead time: resolution_date - created_date
    lead_times = []
    for issue in done_issues:
        if issue.resolution_date and issue.created_date:
            delta = issue.resolution_date - issue.created_date
            lead_times.append(delta.total_seconds() / 3600)
    lead_time_avg = sum(lead_times) / len(lead_times) if lead_times else None
    
    # Cycle time: resolution_date - started_date
    cycle_times = []
    for issue in done_issues:
        if issue.resolution_date and issue.started_date:
            delta = issue.resolution_date - issue.started_date
            cycle_times.append(delta.total_seconds() / 3600)
    cycle_time_avg = sum(cycle_times) / len(cycle_times) if cycle_times else None
    
    # Velocity: sum of story points for done issues
    velocity = sum(issue.story_points or 0.0 for issue in done_issues)
    
    # Completion rate
    total_issues = len(issues)
    completion_rate = (throughput / total_issues * 100) if total_issues > 0 else None
    
    return ProductivityMetrics(
        throughput=throughput,
        lead_time_avg_hours=lead_time_avg,
        cycle_time_avg_hours=cycle_time_avg,
        velocity=velocity,
        completion_rate=completion_rate
    )


# =============================================================================
# Sidebar Rendering (Task 9.2)
# =============================================================================

def render_sidebar(projects: List[Project], sprints: List[Sprint]) -> Filters:
    """
    Render sidebar with filters and return selected filter values.
    
    Args:
        projects: Available projects.
        sprints: Available sprints.
        
    Returns:
        Filters object with selected values.
    """
    return render_filters_sidebar(projects, sprints)


# =============================================================================
# Flow Balance Table (similar to Legacy view)
# =============================================================================

def render_flow_balance_table(issues: List[Issue]):
    """
    Render flow balance table showing entries vs exits by issue type.
    
    Args:
        issues: List of issues to analyze.
    """
    import pandas as pd
    from collections import defaultdict
    
    st.subheader("📉 Balanço de Vazão por Tipo (Entradas vs. Saídas)")
    
    # Group by type
    flow_map: dict[str, dict[str, int]] = defaultdict(lambda: {"entradas": 0, "saidas": 0})
    
    for issue in issues:
        tipo = issue.issue_type or "Outros"
        flow_map[tipo]["entradas"] += 1
        if issue.status_category == "Done":
            flow_map[tipo]["saidas"] += 1
    
    # Create data for table
    data = []
    for tipo, values in sorted(flow_map.items(), key=lambda x: x[1]["entradas"], reverse=True):
        entradas = values["entradas"]
        saidas = values["saidas"]
        saldo = saidas - entradas
        eficiencia = (saidas / entradas * 100) if entradas > 0 else 0
        
        data.append({
            "Tipo": tipo,
            "Novas (Entradas)": entradas,
            "Entregues (Saídas)": saidas,
            "Saldo (Net Flow)": saldo,
            "Status Vazão": "📈 Positiva" if saldo >= 0 else "📉 Negativa",
            "% Eficiência": f"{eficiencia:.1f}%"
        })
    
    if data:
        df = pd.DataFrame(data)
        
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Tipo": st.column_config.TextColumn("Tipo de Item"),
                "Novas (Entradas)": st.column_config.NumberColumn("Novas (Entradas)"),
                "Entregues (Saídas)": st.column_config.NumberColumn("Entregues (Saídas)"),
                "Saldo (Net Flow)": st.column_config.NumberColumn("Saldo (Net Flow)"),
                "Status Vazão": st.column_config.TextColumn("Status de Vazão"),
                "% Eficiência": st.column_config.TextColumn("% Eficiência")
            }
        )
    else:
        st.info("Sem dados para exibir")


# =============================================================================
# Allocation Metrics Section (Task 9.3)
# =============================================================================

def render_allocation_section(
    allocation_metrics: List[AllocationMetrics],
    issues: List[Issue]
):
    """
    Render allocation metrics section with cards and charts.
    
    Args:
        allocation_metrics: Calculated allocation metrics.
        issues: Issues for workload distribution.
    """
    st.subheader("📊 Métricas de Alocação")
    
    if not allocation_metrics:
        st.info("Nenhuma métrica de alocação disponível")
        return
    
    # Summary metrics row
    total_members = len(allocation_metrics)
    overloaded_count = sum(1 for m in allocation_metrics if m.status == AllocationStatus.OVERLOADED)
    underutilized_count = sum(1 for m in allocation_metrics if m.status == AllocationStatus.UNDERUTILIZED)
    avg_allocation = sum(m.allocation_rate for m in allocation_metrics) / total_members if total_members > 0 else 0
    
    # Explanation tooltip
    st.caption("ℹ️ **Como é calculada a Taxa de Alocação:** (Esforço em horas ÷ 24h) × 100%. "
               "O esforço é calculado pelo T-Shirt Size: PP=2.5h, P=6h, M=16h, G=32h, GG=60h, XGG=100h. "
               "Capacidade base: 24h/sprint. Acima de 100% = Sobrecarregado | Abaixo de 50% = Subutilizado")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Membros", total_members,
                 help="Quantidade de membros com issues atribuídas na sprint")
    
    with col2:
        st.metric("Taxa Média de Alocação", f"{avg_allocation:.1f}%",
                 help="Média da taxa de alocação de todos os membros")
    
    with col3:
        st.metric("🔴 Sobrecarregados", overloaded_count,
                 delta=f"+{overloaded_count}" if overloaded_count > 0 else None,
                 delta_color="inverse",
                 help="Membros com taxa de alocação acima de 100%")
    
    with col4:
        st.metric("🟡 Subutilizados", underutilized_count,
                 delta=f"+{underutilized_count}" if underutilized_count > 0 else None,
                 delta_color="inverse",
                 help="Membros com taxa de alocação abaixo de 50%")
    
    st.divider()
    
    # Combined chart section
    st.write("**Visão Geral de Alocação e Tipos de Cards**")
    
    # Calculate type distribution (for reference)
    type_distribution = {}
    for issue in issues:
        issue_type = issue.issue_type or "Outros"
        if issue_type not in type_distribution:
            type_distribution[issue_type] = 0
        type_distribution[issue_type] += 1
    
    render_combined_allocation_chart(allocation_metrics, type_distribution, issues)
    
    # Flow Balance Table (similar to Legacy view)
    st.divider()
    render_flow_balance_table(issues)
    
    # Individual member details (drill-down) - Task 9.5
    st.divider()
    render_allocation_drilldown(allocation_metrics, issues)


def render_allocation_drilldown(
    allocation_metrics: List[AllocationMetrics],
    issues: List[Issue]
):
    """
    Render expandable drill-down for allocation metrics.
    
    Args:
        allocation_metrics: Allocation metrics to display.
        issues: Issues for detailed view.
    """
    st.write("**Detalhamento por Membro** (clique para expandir)")
    
    for metric in allocation_metrics:
        # Status emoji and color
        status_emoji = {
            AllocationStatus.NORMAL: "✅",
            AllocationStatus.OVERLOADED: "🔴",
            AllocationStatus.UNDERUTILIZED: "🟡"
        }.get(metric.status, "⚪")
        
        with st.expander(f"{status_emoji} {metric.entity_name} - {metric.allocation_rate:.1f}%"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Issues Atribuídas", metric.assigned_issues)
            with col2:
                st.metric("Esforço (horas)", f"{metric.total_story_points:.1f}h",
                         help="Baseado no T-Shirt Size das issues")
            with col3:
                st.metric("Status", metric.status.value.title())
            
            # Show member's issues
            member_issues = [i for i in issues if i.assignee_account_id == metric.entity_id]
            if member_issues:
                st.write("**Issues:**")
                from src.models.data_models import get_tshirt_size_label
                issue_data = []
                for issue in member_issues:
                    issue_data.append({
                        "Key": issue.key,
                        "Resumo": issue.summary[:50] + "..." if len(issue.summary) > 50 else issue.summary,
                        "Tipo": issue.issue_type,
                        "Status": issue.status,
                        "Tamanho": get_tshirt_size_label(issue.t_shirt_size),
                        "Criado": issue.created_date.strftime("%d/%m/%Y") if issue.created_date else "-",
                        "Início": issue.started_date.strftime("%d/%m/%Y") if issue.started_date else "-",
                        "Fim": issue.resolution_date.strftime("%d/%m/%Y") if issue.resolution_date else "-"
                    })
                st.dataframe(issue_data, use_container_width=True, hide_index=True)


# =============================================================================
# Productivity Metrics Section (Task 9.4)
# =============================================================================

def render_productivity_section(
    productivity_metrics: ProductivityMetrics,
    sprints: List[Sprint],
    issues: List[Issue]
):
    """
    Render productivity metrics section with cards and charts.
    
    Args:
        productivity_metrics: Calculated productivity metrics.
        sprints: Sprints for velocity chart.
        issues: Issues for trend analysis.
    """
    st.subheader("⚡ Métricas de Produtividade")
    
    # Main metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Throughput", productivity_metrics.throughput,
                 help="Número de issues concluídas")
    
    with col2:
        lead_time_display = f"{productivity_metrics.lead_time_avg_hours:.1f}h" if productivity_metrics.lead_time_avg_hours else "N/A"
        st.metric("Lead Time Médio", lead_time_display,
                 help="Tempo médio desde criação até resolução")
    
    with col3:
        cycle_time_display = f"{productivity_metrics.cycle_time_avg_hours:.1f}h" if productivity_metrics.cycle_time_avg_hours else "N/A"
        st.metric("Cycle Time Médio", cycle_time_display,
                 help="Tempo médio desde início até resolução")
    
    with col4:
        velocity_display = f"{productivity_metrics.velocity:.1f}h" if productivity_metrics.velocity else "N/A"
        st.metric("Velocity (horas)", velocity_display,
                 help="Soma do esforço (horas) das issues concluídas, baseado no T-Shirt Size")
    
    with col5:
        completion_display = f"{productivity_metrics.completion_rate:.1f}%" if productivity_metrics.completion_rate else "N/A"
        st.metric("Taxa de Conclusão", completion_display,
                 help="Percentual de issues concluídas")
    
    st.divider()
    
    # Charts section - Velocity Trend
    st.write("**Tendência de Velocity (por semana)**")
    
    # Calculate velocity trends from issues
    trends = []
    if issues:
        # Group issues by week and calculate velocity
        done_issues = [i for i in issues if i.status_category == "Done" and i.resolution_date]
        if done_issues:
            from collections import defaultdict
            weekly_velocity = defaultdict(float)
            weekly_count = defaultdict(int)
            for issue in done_issues:
                week_start = issue.resolution_date.date() - timedelta(days=issue.resolution_date.weekday())
                weekly_velocity[week_start] += issue.story_points or 0  # story_points = hours from T-Shirt Size
                weekly_count[week_start] += 1
            
            for week_date, velocity in sorted(weekly_velocity.items())[-8:]:
                trends.append(MetricTrend(date=week_date, value=velocity, metric_type="velocity"))
    
    if trends:
        render_trend_chart(trends, "Velocity (horas)")
    else:
        st.info("Sem dados de tendência disponíveis - nenhuma issue concluída com data de resolução")
    
    # Productivity drill-down - Task 9.5
    st.divider()
    render_productivity_drilldown(productivity_metrics, issues)


def render_productivity_drilldown(
    productivity_metrics: ProductivityMetrics,
    issues: List[Issue]
):
    """
    Render expandable drill-down for productivity metrics.
    
    Args:
        productivity_metrics: Productivity metrics to display.
        issues: Issues for detailed view.
    """
    st.write("**Detalhamento de Produtividade** (clique para expandir)")
    
    with st.expander("📈 Throughput - Issues Concluídas"):
        done_issues = [i for i in issues if i.status_category == "Done"]
        if done_issues:
            from src.models.data_models import get_tshirt_size_label
            issue_data = []
            for issue in done_issues:
                issue_data.append({
                    "Key": issue.key,
                    "Resumo": issue.summary[:40] + "..." if len(issue.summary) > 40 else issue.summary,
                    "Tipo": issue.issue_type,
                    "Tamanho": get_tshirt_size_label(issue.t_shirt_size),
                    "Responsável": issue.assignee_name or "N/A",
                    "Criado": issue.created_date.strftime("%d/%m/%Y") if issue.created_date else "-",
                    "Início": issue.started_date.strftime("%d/%m/%Y") if issue.started_date else "-",
                    "Fim": issue.resolution_date.strftime("%d/%m/%Y") if issue.resolution_date else "-"
                })
            st.dataframe(issue_data, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma issue concluída")
    
    with st.expander("⏱️ Lead Time - Detalhes"):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Lead Time Médio:**")
            if productivity_metrics.lead_time_avg_hours:
                days = productivity_metrics.lead_time_avg_hours / 24
                st.write(f"- {productivity_metrics.lead_time_avg_hours:.1f} horas")
                st.write(f"- {days:.1f} dias")
            else:
                st.write("N/A - Dados insuficientes")
        
        with col2:
            st.write("**Interpretação:**")
            if productivity_metrics.lead_time_avg_hours:
                if productivity_metrics.lead_time_avg_hours > 168:  # > 1 week
                    st.warning("Lead time alto - considere revisar o processo")
                elif productivity_metrics.lead_time_avg_hours > 72:  # > 3 days
                    st.info("Lead time moderado")
                else:
                    st.success("Lead time saudável")
    
    with st.expander("🔄 Cycle Time - Detalhes"):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Cycle Time Médio:**")
            if productivity_metrics.cycle_time_avg_hours:
                days = productivity_metrics.cycle_time_avg_hours / 24
                st.write(f"- {productivity_metrics.cycle_time_avg_hours:.1f} horas")
                st.write(f"- {days:.1f} dias")
            else:
                st.write("N/A - Dados insuficientes")
        
        with col2:
            st.write("**Interpretação:**")
            if productivity_metrics.cycle_time_avg_hours:
                if productivity_metrics.cycle_time_avg_hours > 72:  # > 3 days
                    st.warning("Cycle time alto - possíveis bloqueios")
                elif productivity_metrics.cycle_time_avg_hours > 24:  # > 1 day
                    st.info("Cycle time moderado")
                else:
                    st.success("Cycle time excelente")


# =============================================================================
# Export Section
# =============================================================================

def render_export_section(
    allocation_metrics: List[AllocationMetrics],
    productivity_metrics: ProductivityMetrics,
    issues: List[Issue]
):
    """
    Render export buttons for CSV download.
    
    Args:
        allocation_metrics: Allocation data to export.
        productivity_metrics: Productivity data to export.
        issues: Issues to export.
    """
    st.subheader("📥 Exportar Dados")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export allocation metrics
        allocation_data = []
        for m in allocation_metrics:
            allocation_data.append({
                "Membro": m.entity_name,
                "Taxa de Alocação (%)": m.allocation_rate,
                "Issues Atribuídas": m.assigned_issues,
                "Esforço (horas)": m.total_story_points,
                "Status": m.status.value
            })
        render_export_button(allocation_data, "allocation_metrics.csv", "📊 Exportar Alocação")
    
    with col2:
        # Export productivity metrics
        productivity_data = [{
            "Throughput": productivity_metrics.throughput,
            "Lead Time (h)": productivity_metrics.lead_time_avg_hours or "N/A",
            "Cycle Time (h)": productivity_metrics.cycle_time_avg_hours or "N/A",
            "Velocity (horas)": productivity_metrics.velocity or "N/A",
            "Taxa de Conclusão (%)": productivity_metrics.completion_rate or "N/A"
        }]
        render_export_button(productivity_data, "productivity_metrics.csv", "⚡ Exportar Produtividade")
    
    with col3:
        # Export issues
        from src.models.data_models import get_tshirt_size_label
        issues_data = []
        for issue in issues:
            issues_data.append({
                "Key": issue.key,
                "Resumo": issue.summary,
                "Tipo": issue.issue_type,
                "Status": issue.status,
                "Responsável": issue.assignee_name or "N/A",
                "Tamanho": get_tshirt_size_label(issue.t_shirt_size),
                "Esforço (h)": issue.story_points or 0,
                "Criado": issue.created_date.strftime("%Y-%m-%d") if issue.created_date else "N/A"
            })
        render_export_button(issues_data, "issues.csv", "📋 Exportar Issues")


# =============================================================================
# AI Analysis Section
# =============================================================================

def render_ai_analysis_section(
    allocation_metrics: List[AllocationMetrics],
    productivity_metrics: ProductivityMetrics
):
    """
    Render AI-powered analysis section.
    
    Args:
        allocation_metrics: Team allocation metrics
        productivity_metrics: Productivity metrics
    """
    st.subheader("🤖 Análise de IA")
    
    # Check if AI is available
    assistant = get_ai_assistant()
    
    if not assistant:
        st.warning("⚠️ Análise de IA não disponível. Configure a variável OPENAI_API_KEY no arquivo .env")
        return
    
    # Initialize session state for AI analysis
    if "ai_analysis" not in st.session_state:
        st.session_state.ai_analysis = None
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🔄 Gerar Análise", type="primary"):
            with st.spinner("Analisando métricas com IA..."):
                analysis = assistant.analyze_allocation(allocation_metrics, productivity_metrics)
                st.session_state.ai_analysis = analysis
    
    with col1:
        st.caption("Clique no botão para gerar uma análise inteligente das métricas do time")
    
    # Display analysis if available
    if st.session_state.ai_analysis:
        st.markdown("---")
        st.markdown(st.session_state.ai_analysis)


# =============================================================================
# Configuration/Status Page (Task 9.7)
# =============================================================================

def render_configuration_page(
    config: Optional[AppConfig],
    connection_status: ConnectionStatus
):
    """
    Render configuration and status page.
    
    Args:
        config: Application configuration.
        connection_status: Current connection status.
    """
    from src.ui.components import (
        render_loading_skeleton,
        render_loading_card_skeleton,
    )
    
    st.header("⚙️ Configuração e Status")
    
    # Connection Status Section
    st.subheader("🔌 Status da Conexão")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if connection_status.connected:
            st.success("✅ Conectado ao Jira")
            if connection_status.server_info:
                st.write(f"**Servidor:** {connection_status.server_info.get('serverTitle', 'N/A')}")
                st.write(f"**Versão:** {connection_status.server_info.get('version', 'N/A')}")
        else:
            st.warning("⚠️ Não conectado ao Jira")
            st.write(f"**Motivo:** {connection_status.error_message or 'Credenciais não configuradas'}")
            st.info("💡 Configure as variáveis de ambiente JIRA_BASE_URL, JIRA_USERNAME e JIRA_API_TOKEN")
    
    with col2:
        st.write("**Última Verificação:**")
        st.write(connection_status.last_checked.strftime("%Y-%m-%d %H:%M:%S"))
        
        if st.button("🔄 Testar Conexão", type="primary"):
            if st.session_state.connector:
                # Show loading while testing connection
                loading_placeholder = st.empty()
                with loading_placeholder.container():
                    render_loading_skeleton(1, "40px", "Testando conexão com o Jira...")
                
                new_status = test_jira_connection(st.session_state.connector)
                st.session_state.connection_status = new_status
                loading_placeholder.empty()
                st.rerun()
            else:
                st.warning("Conector não inicializado. Verifique as credenciais.")
    
    st.divider()
    
    # Application Info Section
    st.subheader("📱 Informações da Aplicação")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Versão", APP_VERSION)
    
    with col2:
        # Get cache stats once
        cache_stats = CacheManager.get_cache_stats()
        st.metric("Entradas em Cache", cache_stats["valid_entries"])
    
    with col3:
        st.metric("Modo Demo", "Ativo" if st.session_state.demo_mode else "Inativo")
    
    with col4:
        # MongoDB status
        from src.cache.mongo_cache import MongoCacheManager
        mongodb_enabled = MongoCacheManager.is_enabled()
        if mongodb_enabled:
            st.metric("MongoDB", "✅ Conectado", help="Cache persistente ativo")
        else:
            st.metric("MongoDB", "⚠️ Offline", help="Usando cache em memória")
    
    st.divider()
    
    # Configuration Details Section
    st.subheader("📝 Configuração Atual")
    
    if config:
        with st.expander("Ver Configuração", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Cache TTL:** {config.cache_ttl_seconds} segundos")
                st.write(f"**Projetos:** {', '.join(config.projects) if config.projects else 'Nenhum'}")
            
            with col2:
                st.write(f"**Capacidade:** {config.default_capacity_hours} horas/sprint")
                st.write(f"**Jira URL:** {config.jira.base_url}")
    else:
        st.warning("Configuração não carregada")
    
    st.divider()
    
    # Cache Management
    st.subheader("🗑️ Gerenciamento de Cache")
    
    st.caption("O cache é compartilhado entre todos os usuários (TTL: 1 hora)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Cache de sessão:** {cache_stats['session_entries']} entradas")
        if cache_stats.get('mongodb_enabled'):
            st.write(f"**Cache MongoDB:** {cache_stats.get('mongodb_entries', 0)} entradas")
        else:
            st.write("**Cache MongoDB:** Desabilitado")
        st.write("**Cache compartilhado:** @st.cache_data (1h TTL)")
    
    with col2:
        if st.button("🗑️ Limpar Todo Cache", type="secondary"):
            # Show loading while clearing cache
            loading_placeholder = st.empty()
            with loading_placeholder.container():
                render_loading_skeleton(1, "40px", "Limpando cache...")
            
            # Limpar cache de sessão
            cleared = CacheManager.clear_all()
            # Limpar cache compartilhado
            clear_all_caches()
            # Reset preload flag to allow new preload
            st.session_state.professionals_preload_started = False
            loading_placeholder.empty()
            st.success(f"Cache limpo! Sessão: {cleared} entradas. Cache compartilhado: resetado.")
            st.rerun()


# =============================================================================
# Professional View Tab (Task 4)
# =============================================================================

def render_professional_view_tab(
    connector: Optional[JiraConnector],
    config: Optional[AppConfig],
    connection_status: ConnectionStatus
):
    """
    Render the Professional View tab with allocation metrics per professional.
    """
    from src.ui.components import (
        render_loading_skeleton,
        render_loading_card_skeleton,
        render_loading_selector_skeleton
    )
    
    # Check if connected
    if not connection_status.connected:
        st.warning(
            "⚠️ Não conectado ao Jira. Conecte-se na aba Configuração para "
            "visualizar a alocação por profissional."
        )
        return
    
    # Check if connector is available
    if not connector:
        st.error("❌ Conector Jira não disponível. Verifique a configuração.")
        return
    
    # Get Jira config for cache key
    jira_base_url = config.jira.base_url if config else ""
    default_capacity = config.default_capacity_hours if config else 24.0
    
    # Load professionals first (needed for the filter)
    try:
        all_projects = get_all_projects_cached(
            connector=connector,
            base_url=jira_base_url
        )
        project_keys = [p.key for p in all_projects]
    except Exception as e:
        st.error(f"❌ Erro ao carregar projetos do Jira: {str(e)}")
        return
    
    if not project_keys:
        st.info("ℹ️ Nenhum projeto disponível.")
        return
    
    # Date filters, professional selector and refresh button
    with st.expander("🔍 Filtros", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            prof_start_date = st.date_input(
                "Data Início",
                value=None,
                key="prof_filter_start_date",
                help="Filtrar issues criadas a partir desta data"
            )
        
        with col2:
            prof_end_date = st.date_input(
                "Data Fim",
                value=None,
                key="prof_filter_end_date",
                help="Filtrar issues criadas até esta data"
            )
        
        # Build date range for professional view
        prof_date_range = None
        if prof_start_date or prof_end_date:
            prof_date_range = DateRange(
                start=prof_start_date,
                end=prof_end_date
            )
        
        # Load professionals with date filter
        try:
            professionals = get_all_professionals_cached(
                connector=connector,
                project_keys=project_keys,
                default_capacity=default_capacity,
                base_url=jira_base_url,
                date_range=prof_date_range
            )
        except Exception as e:
            st.error(f"❌ Erro ao carregar profissionais: {str(e)}")
            return
        
        # Professional selector
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if professionals:
                prof_options = {
                    p.account_id: f"{p.display_name} ({p.project_count} projeto{'s' if p.project_count != 1 else ''})"
                    for p in professionals
                }
                account_ids = [""] + list(prof_options.keys())
                
                selected_professional_id = st.selectbox(
                    "👤 Profissional",
                    options=account_ids,
                    format_func=lambda x: "Selecione um profissional..." if not x else prof_options.get(x, x),
                    key="prof_filter_professional"
                )
            else:
                selected_professional_id = None
                st.info("Nenhum profissional disponível.")
        
        with col2:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("🔄 Atualizar", key="refresh_professionals"):
                clear_professionals_cache()
                st.session_state.professionals_preload_started = False
                st.rerun()
    
    # Show active filter info
    filter_parts = []
    if prof_start_date:
        filter_parts.append(f"De: {prof_start_date.strftime('%d/%m/%Y')}")
    if prof_end_date:
        filter_parts.append(f"Até: {prof_end_date.strftime('%d/%m/%Y')}")
    if filter_parts:
        st.caption(f"🔍 {' | '.join(filter_parts)}")
    
    st.caption(f"📁 {len(project_keys)} projetos | 👥 {len(professionals)} profissionais")
    
    # Check if professional is selected
    if not selected_professional_id:
        st.info("👆 Selecione um profissional no filtro acima para visualizar sua alocação.")
        return
    
    # Instantiate ProfessionalMetricsEngine for rendering
    try:
        metrics_engine = ProfessionalMetricsEngine(
            connector=connector,
            cache=CacheManager,
            default_capacity=default_capacity,
            date_range=prof_date_range
        )
    except Exception as e:
        st.error(f"❌ Erro ao inicializar engine de métricas: {str(e)}")
        return
    
    # Render the professional view content (without the selector, which is now in filters)
    render_professional_view_content(
        selected_professional_id=selected_professional_id,
        professionals=professionals,
        metrics_engine=metrics_engine
    )


# =============================================================================
# Main Dashboard Content (Task 9.1, 9.6)
# =============================================================================

def render_dashboard_content(
    filters: Filters,
    projects: List[Project],
    sprints: List[Sprint],
    connection_status: ConnectionStatus
):
    """
    Render main dashboard content with metrics and charts.
    
    This function handles real-time updates when filters change (Task 9.6).
    
    Args:
        filters: Current filter selections.
        projects: Available projects.
        sprints: Available sprints.
        connection_status: Current connection status.
    """
    # Header and description
    st.header("📊 Visão por Projeto")
    st.markdown(
        "Visualize métricas de alocação e produtividade por projeto e sprint."
    )
    
    st.divider()
    
    # Check if connected
    if not connection_status.connected:
        st.warning("⚠️ Não conectado ao Jira. Verifique as credenciais na aba Configuração.")
        return
    
    # Check if project is selected
    if not filters.project_keys:
        st.info("👆 Selecione um ou mais projetos no filtro acima para visualizar as métricas.")
        return
    
    # Check if at least one filter (sprint or date) is selected
    has_sprint_filter = bool(filters.sprint_ids)
    has_date_filter = filters.date_range and (filters.date_range.start or filters.date_range.end)
    
    if not has_sprint_filter and not has_date_filter:
        st.info("👆 Selecione uma sprint e/ou um período de datas para visualizar as métricas.")
        return
    
    # Load data based on filters (Task 9.6 - real-time update)
    connector = st.session_state.connector
    config = st.session_state.config
    
    # Show current filter info
    filter_parts = [f"Projetos: {', '.join(filters.project_keys)}"]
    if filters.sprint_ids:
        filter_parts.append(f"Sprints: {len(filters.sprint_ids)} selecionada(s)")
    if filters.date_range:
        if filters.date_range.start:
            filter_parts.append(f"De: {filters.date_range.start.strftime('%d/%m/%Y')}")
        if filters.date_range.end:
            filter_parts.append(f"Até: {filters.date_range.end.strftime('%d/%m/%Y')}")
    st.caption(f"🔍 {' | '.join(filter_parts)}")
    
    with st.spinner("Carregando issues do Jira..."):
        issues = load_issues(connector, filters)
    
    if not issues:
        st.warning(f"Nenhuma issue encontrada para os projetos selecionados no período especificado.")
        return
    
    st.success(f"✅ {len(issues)} issues carregadas")
    
    # Calculate metrics
    allocation_metrics = calculate_allocation_metrics(issues, filters)
    productivity_metrics = calculate_productivity_metrics(issues)
    
    # Render sections
    st.divider()
    
    # Allocation Section (Task 9.3)
    render_allocation_section(allocation_metrics, issues)
    
    st.divider()
    
    # Productivity Section (Task 9.4)
    render_productivity_section(productivity_metrics, sprints, issues)
    
    st.divider()
    
    # AI Analysis Section (controlled by AI_ENABLED env var)
    import os
    if os.getenv("AI_ENABLED", "false").lower() == "true":
        render_ai_analysis_section(allocation_metrics, productivity_metrics)
        st.divider()
    
    # Export Section - hidden for now
    # render_export_section(allocation_metrics, productivity_metrics, issues)


# =============================================================================
# Main Application Entry Point (Task 9.1)
# =============================================================================

def main():
    """Main application entry point."""
    # Check access first
    if not check_access():
        return
    
    # Initialize session state
    init_session_state()
    
    # Apply custom theme
    apply_custom_theme()
    
    # Load configuration
    if st.session_state.config is None:
        config = load_configuration()
        st.session_state.config = config
    else:
        config = st.session_state.config
    
    # Initialize Jira connector (with graceful handling)
    if st.session_state.connector is None and config:
        connector = initialize_jira_connector(config)
        st.session_state.connector = connector
        
        if connector:
            # Test connection
            connection_status = test_jira_connection(connector)
            st.session_state.connection_status = connection_status
            st.session_state.demo_mode = not connection_status.connected
        else:
            st.session_state.demo_mode = True
    
    connector = st.session_state.connector
    connection_status = st.session_state.connection_status
    
    # Load projects and sprints
    projects = load_projects(connector, config)
    sprints = load_sprints(connector)
    
    # Start background preload of professionals (non-blocking)
    if connection_status.connected and connector and config:
        if "professionals_preload_started" not in st.session_state:
            st.session_state.professionals_preload_started = False
        
        if not st.session_state.professionals_preload_started:
            st.session_state.professionals_preload_started = True
            # Start background thread for preloading
            import threading
            
            def preload_professionals_background():
                """Preload professionals in background thread."""
                try:
                    jira_base_url = config.jira.base_url
                    default_capacity = config.default_capacity_hours
                    
                    # Get all project keys
                    all_projects = get_all_projects_cached(
                        connector=connector,
                        base_url=jira_base_url
                    )
                    project_keys = [p.key for p in all_projects]
                    
                    if project_keys:
                        get_all_professionals_cached(
                            connector=connector,
                            project_keys=project_keys,
                            default_capacity=default_capacity,
                            base_url=jira_base_url
                        )
                except Exception:
                    pass  # Silently fail - user can still load manually
            
            thread = threading.Thread(target=preload_professionals_background, daemon=True)
            thread.start()
    
    # Header with dark background similar to Efí website
    status_badge = "🟢 Conectado ao Jira" if connection_status.connected else "🔴 Desconectado"
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #1A1A1A 0%, #2D2D2D 100%);
            padding: 1rem 2rem;
            margin: -1rem -2rem 1rem -2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        ">
            <div style="display: flex; align-items: center; gap: 2rem;">
                <img src="https://sejaefi.com.br/_ipx/_/images/paginas/common/logos/logo-efi-bank-orange.svg" 
                     alt="Efí" style="height: 32px;">
                <span style="color: #9CA3AF; font-size: 0.9rem; font-weight: 500;">Acompanhamento Jira</span>
            </div>
            <div style="
                background: {'rgba(34, 197, 94, 0.15)' if connection_status.connected else 'rgba(239, 68, 68, 0.15)'};
                color: {'#22C55E' if connection_status.connected else '#EF4444'};
                padding: 0.4rem 1rem;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 500;
            ">{status_badge}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Main content area with tabs (Dashboard, Professional View, Legacy, Configuration)
    tab_dashboard, tab_professional, tab_legacy, tab_config = st.tabs([
        "📊 Visão por Projeto", 
        "👤 Visão por Profissional",
        "📋 Legado",
        "⚙️ Configuração"
    ])
    
    # Renderizar tabs na ordem que funciona (Legado e Config primeiro)
    with tab_legacy:
        render_legacy_view(connector, config, connection_status)
    
    with tab_config:
        render_configuration_page(config, connection_status)
    
    with tab_dashboard:
        filters = render_inline_filters(projects, sprints)
        
        # Store current filter state to detect changes
        current_filter_key = f"{filters.project_keys}_{filters.sprint_ids}"
        if "last_dashboard_filter_key" not in st.session_state:
            st.session_state.last_dashboard_filter_key = None
        
        # Check if filters changed
        if st.session_state.last_dashboard_filter_key != current_filter_key:
            st.session_state.last_dashboard_filter_key = current_filter_key
        
        render_dashboard_content(filters, projects, sprints, connection_status)
    
    with tab_professional:
        render_professional_view_tab(connector, config, connection_status)


def render_inline_filters(projects: List[Project], sprints: List[Sprint]) -> Filters:
    """
    Render inline filters at the top of the dashboard tab.
    
    Args:
        projects: Available projects
        sprints: Available sprints
        
    Returns:
        Filters object with selected values
    """
    with st.expander("🔍 Filtros", expanded=True):
        col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 1.5, 0.8])
        
        with col1:
            # Project filter
            project_options = {p.key: f"{p.key} - {p.name}" for p in projects}
            
            if project_options:
                selected_projects = st.multiselect(
                    "Projetos",
                    options=list(project_options.keys()),
                    format_func=lambda x: project_options.get(x, x),
                    key="inline_filter_projects",
                    help=f"{len(projects)} projetos disponíveis",
                    placeholder="Selecione os projetos"
                )
            else:
                selected_projects = []
                st.warning("⚠️ Nenhum projeto disponível")
        
        with col2:
            # Sprint filter - only enabled when projects are selected
            if not selected_projects:
                # No project selected - show disabled empty multiselect
                selected_sprint_ids = st.multiselect(
                    "Sprints",
                    options=[],
                    key="inline_filter_sprints",
                    disabled=True,
                    help="Selecione um projeto primeiro",
                    placeholder="Selecione um projeto primeiro"
                )
            else:
                # Projects selected - load sprints for those projects
                available_sprints = []
                if "connector" in st.session_state and st.session_state.connector:
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
                    
                    # Sort sprints
                    state_order = {"active": 0, "future": 1, "closed": 2}
                    unique_sprints.sort(key=lambda s: (
                        state_order.get(s.state, 3),
                        -(s.start_date.timestamp() if s.start_date else 0)
                    ))
                    available_sprints = unique_sprints
                
                sprint_options = {s.jira_id: f"{s.name} ({s.state})" for s in available_sprints}
                
                selected_sprint_ids = st.multiselect(
                    "Sprints",
                    options=list(sprint_options.keys()),
                    format_func=lambda x: sprint_options.get(x, str(x)),
                    key="inline_filter_sprints",
                    help=f"{len(available_sprints)} sprints disponíveis" if available_sprints else "Nenhum sprint encontrado",
                    placeholder="Selecione os sprints"
                )
        
        with col3:
            # Data início
            start_date = st.date_input(
                "Data Início",
                value=None,
                key="inline_filter_start_date",
                help="Filtrar issues criadas a partir desta data"
            )
        
        with col4:
            # Data fim
            end_date = st.date_input(
                "Data Fim",
                value=None,
                key="inline_filter_end_date",
                help="Filtrar issues criadas até esta data"
            )
        
        with col5:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("🗑️ Limpar", key="inline_clear_filters"):
                st.rerun()
    
    # Build date range if dates are selected
    date_range = None
    if start_date or end_date:
        date_range = DateRange(
            start=start_date,
            end=end_date
        )
    
    return Filters(
        project_keys=selected_projects,
        sprint_ids=selected_sprint_ids,
        date_range=date_range,
        assignees=[]
    )


if __name__ == "__main__":
    main()
