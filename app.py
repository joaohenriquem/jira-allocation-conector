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

# Initialize Sentry for error monitoring (before other imports)
from src.utils.sentry_config import init_sentry, capture_exception, capture_message, set_user_context
sentry_initialized = init_sentry()

from src.utils.crypto import encrypt, decrypt, mask_email, mask_ip

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
from src.ui.cycle_view import render_cycle_view_tab
from src.ui.report_view import render_report_tab
from src.metrics.professional_metrics import ProfessionalMetricsEngine
from src.config.teams_loader import load_teams, get_team_names, get_team_members_by_name, find_team_for_member
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

def get_allowed_ips() -> list:
    """
    Get list of allowed IPs from secrets or environment.
    Returns empty list if IP filtering is disabled.
    """
    try:
        # Try Streamlit secrets first
        allowed_ips = st.secrets.get("ALLOWED_IPS", "")
    except Exception:
        # Fallback to environment variable
        import os
        allowed_ips = os.getenv("ALLOWED_IPS", "")
    
    if not allowed_ips:
        return []
    
    # Parse comma-separated IPs
    return [ip.strip() for ip in allowed_ips.split(",") if ip.strip()]


def get_client_ip() -> str:
    """
    Get client IP address using external service.
    Returns empty string if unable to determine.
    """
    import urllib.request
    import json
    
    try:
        # Use ipify API to get client IP
        with urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5) as response:
            data = json.loads(response.read().decode())
            return data.get("ip", "")
    except Exception:
        try:
            # Fallback to httpbin
            with urllib.request.urlopen("https://httpbin.org/ip", timeout=5) as response:
                data = json.loads(response.read().decode())
                return data.get("origin", "").split(",")[0].strip()
        except Exception:
            return ""


def check_ip_access() -> tuple[bool, str]:
    """
    Check if client IP is allowed.
    Returns (is_allowed, client_ip).
    If no IPs configured, allows all.
    """
    allowed_ips = get_allowed_ips()
    
    # If no IPs configured, skip IP check
    if not allowed_ips:
        return True, ""
    
    client_ip = get_client_ip()
    
    if not client_ip:
        # Could not determine IP - deny access for security
        return False, "desconhecido"
    
    # Check if client IP is in allowed list
    is_allowed = client_ip in allowed_ips
    return is_allowed, client_ip


def _is_localhost() -> bool:
    """Check if the app is running on localhost."""
    try:
        # Use Streamlit context headers - most reliable method
        host = st.context.headers.get("Host", "")
        return host.startswith("localhost") or host.startswith("127.0.0.1")
    except Exception:
        # If st.context is not available, assume NOT localhost (safer for production)
        return False


def check_access() -> bool:
    """
    Check if user has access to the application.
    Returns True if authenticated, False otherwise.
    Skips authentication on localhost.
    """
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    # Skip auth on localhost (unless user explicitly logged out)
    if not st.session_state.authenticated and _is_localhost() and not st.session_state.get("logged_out"):
        st.session_state.authenticated = True
        st.session_state.user_email = encrypt("dev@localhost")
        st.session_state.ip_checked = True
        st.session_state.ip_allowed = True
        capture_message("Acesso local (localhost)", level="error", extra={
            "email": mask_email("dev@localhost"),
            "ip": "127.0.0.1",
            "tipo": "login_localhost"
        })
        import sentry_sdk
        print(f"[ACESSO] Login localhost | email=dev@localhost | ip=127.0.0.1 | sentry_initialized={sentry_initialized}")
        sentry_sdk.flush(timeout=5)
        return True
    
    if st.session_state.authenticated:
        # Set Sentry user context for existing sessions
        if "user_email" in st.session_state:
            _decrypted_email = decrypt(st.session_state.user_email)
            set_user_context(email=mask_email(_decrypted_email))
        # Log session access (only once per session)
        if not st.session_state.get("_access_logged"):
            _email_raw = decrypt(st.session_state.get("user_email", ""))
            _email_masked = mask_email(_email_raw)
            print(f"[ACESSO] Sessão ativa | email={_email_masked}")
            capture_message("Sessão ativa", level="error", extra={
                "email": _email_masked,
                "tipo": "session_active"
            })
            import sentry_sdk
            sentry_sdk.flush(timeout=5)
            st.session_state._access_logged = True
        return True
    
    # Check IP and get client IP for display
    if "ip_checked" not in st.session_state:
        with st.spinner("Verificando acesso..."):
            ip_allowed, client_ip = check_ip_access()
            # Always try to get client IP for display
            if not client_ip:
                client_ip = get_client_ip()
            st.session_state.ip_checked = True
            st.session_state.ip_allowed = ip_allowed
            st.session_state.client_ip = encrypt(client_ip) if client_ip else ""
    
    if not st.session_state.ip_allowed:
        _masked_ip = mask_ip(decrypt(st.session_state.get("client_ip", "")))
        capture_message("Acesso bloqueado por IP", level="error", extra={
            "ip": _masked_ip,
            "tipo": "ip_blocked"
        })
        import sentry_sdk
        print(f"[ACESSO] IP bloqueado | ip={st.session_state.get('client_ip', 'desconhecido')}")
        sentry_sdk.flush(timeout=5)
        st.error("🚫 Acesso não autorizado.")
        st.stop()
        return False
    
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
    
    # Custom CSS for orange button
    st.markdown(
        """
        <style>
        /* Orange button for form submit */
        div[data-testid="stForm"] button[type="submit"],
        div[data-testid="stFormSubmitButton"] button,
        .stFormSubmitButton button {
            background-color: #F37021 !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
        }
        div[data-testid="stForm"] button[type="submit"]:hover,
        div[data-testid="stFormSubmitButton"] button:hover,
        .stFormSubmitButton button:hover {
            background-color: #E05A10 !important;
            border: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Logo Efí
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="https://sejaefi.com.br/_ipx/_/images/paginas/common/logos/logo-efi-bank-orange.svg" alt="Efí" style="width: 150px;">
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown("### Acesso ao Sistema")
        st.markdown("Digite seu email corporativo para continuar.")
        
        # Show client IP
        client_ip = ""
        # 1. Try Streamlit headers
        try:
            xff = st.context.headers.get("X-Forwarded-For", "")
            if xff:
                ips = [ip.strip() for ip in xff.split(",")]
                for ip in ips:
                    if not ip.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                                          "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                                          "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                                          "172.30.", "172.31.", "192.168.", "127.")):
                        client_ip = ip
                        break
        except Exception:
            pass
        # 2. Try X-Real-Ip
        if not client_ip:
            try:
                client_ip = st.context.headers.get("X-Real-Ip", "")
            except Exception:
                pass
        # 3. Fallback: server-side ipify (returns server IP on cloud)
        if not client_ip:
            client_ip = get_client_ip()
        # 4. Last resort: show internal IP from headers
        if not client_ip:
            try:
                xff = st.context.headers.get("X-Forwarded-For", "")
                if xff:
                    client_ip = xff.split(",")[0].strip()
            except Exception:
                pass
        
        st.caption(f"🌐 IP: `{client_ip}`" if client_ip else "🌐 IP: não identificado")
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="seu.email@sejaefi.com.br")
            password = st.text_input("Senha", type="password", placeholder="Digite a senha de acesso")
            submitted = st.form_submit_button("Entrar", width="stretch", type="primary")
            
            # Rate limiting: max 5 attempts per session
            if "login_attempts" not in st.session_state:
                st.session_state.login_attempts = 0
            
            if submitted:
                if st.session_state.login_attempts >= 5:
                    st.error("🔒 Muitas tentativas. Aguarde alguns minutos.")
                    return False
                
                st.session_state.login_attempts = st.session_state.get("login_attempts", 0) + 1
                try:
                    _access_password = st.secrets.get("ACCESS_PASSWORD", "")
                except Exception:
                    _access_password = ""
                if not _access_password:
                    import os as _os
                    _access_password = _os.getenv("ACCESS_PASSWORD", "")
                if not _access_password:
                    st.error("⚠️ Sistema indisponível.")
                elif password != _access_password:
                    capture_message("Tentativa de login com senha incorreta", level="error", extra={
                        "email": mask_email(email.lower().strip()) if email else "vazio",
                        "ip": mask_ip(client_ip) if client_ip else "desconhecido",
                        "tipo": "wrong_password"
                    })
                    import sentry_sdk
                    print(f"[ACESSO] Senha incorreta | email={mask_email(email)} | ip={mask_ip(client_ip)}")
                    sentry_sdk.flush(timeout=5)
                    st.error("Senha incorreta.")
                elif email:
                    email_lower = email.lower().strip()
                    if email_lower.endswith("@sejaefi.com.br") or email_lower.endswith("@gerencianet.com.br"):
                        st.session_state.authenticated = True
                        st.session_state.user_email = encrypt(email_lower)
                        # Set Sentry user context
                        set_user_context(email=mask_email(email_lower))
                        capture_message("Login autorizado", level="error", extra={
                            "email": mask_email(email_lower),
                            "ip": mask_ip(client_ip),
                            "tipo": "login_success"
                        })
                        import sentry_sdk
                        print(f"[ACESSO] Login autorizado | email={mask_email(email_lower)} | ip={mask_ip(client_ip)}")
                        sentry_sdk.flush(timeout=5)
                        st.rerun()
                    else:
                        capture_message("Tentativa de login com email não autorizado", level="error", extra={
                            "email": mask_email(email_lower),
                            "ip": mask_ip(client_ip),
                            "tipo": "login_denied"
                        })
                        import sentry_sdk
                        print(f"[ACESSO] Login NEGADO | email={mask_email(email_lower)} | ip={mask_ip(client_ip)}")
                        sentry_sdk.flush(timeout=5)
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
        st.warning("⚠️ Arquivo de configuração não encontrado.")
        return None
    except ValueError as e:
        st.error("❌ Erro na configuração. Verifique os parâmetros.")
        return None
    except Exception as e:
        st.error("❌ Erro ao carregar configuração.")
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
        st.error("❌ Erro ao inicializar conector Jira. Verifique as credenciais.")
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
            st.warning("⚠️ Erro ao carregar projetos.")
    
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


def _build_infra_jql(filters: Filters) -> str:
    """Build JQL specific to the INFRA project (service desk requests)."""
    infra_request_types = [
        "Obter ajuda da Infra-Financeira (INFRA)",
        "Obter ajuda da Infra-Cloud (INFRA)",
        "Obter ajuda da Infra-Cloud com erros em projetos e aplicações na nuvem (INFRA)",
        "Obter ajuda da Infra-Cloud com Alteração de parâmetros (INFRA)",
        "Obter ajuda da Infra-Cloud com Deploy de novos projetos (INFRA)",
        "Obter ajuda da Infra-Cloud com alertas e monitoramento (INFRA)",
        "Obter ajuda da Infra-Cloud com Criação de recursos na nuvem (INFRA)",
        "Obter ajuda da Infra-Cloud Operações (Outros) (INFRA)",
    ]
    request_types_str = ", ".join(f'"{rt}"' for rt in infra_request_types)
    
    jql_parts = [
        "project = INFRA",
        "assignee = empty",
        'status NOT IN (Cancelado, Closed, Completed, "Concluído", Resolved)',
        f'"request type" IN ({request_types_str})',
    ]
    
    # Date range filter
    if filters.date_range:
        if filters.date_range.start and filters.date_range.end:
            start_str = filters.date_range.start.strftime("%Y-%m-%d")
            end_str = filters.date_range.end.strftime("%Y-%m-%d")
            jql_parts.append(
                f"((created >= '{start_str}' AND created <= '{end_str}') "
                f"OR (updated >= '{start_str}' AND updated <= '{end_str}'))"
            )
        else:
            if filters.date_range.start:
                start_str = filters.date_range.start.strftime("%Y-%m-%d")
                jql_parts.append(f"(created >= '{start_str}' OR updated >= '{start_str}')")
            if filters.date_range.end:
                end_str = filters.date_range.end.strftime("%Y-%m-%d")
                jql_parts.append(f"(created <= '{end_str}' OR updated <= '{end_str}')")
    
    jql = " AND ".join(jql_parts)
    return f"{jql} ORDER BY priority DESC, updated DESC"


def _build_default_jql(filters: Filters) -> str:
    """Build default JQL for non-INFRA projects."""
    jql_parts = []
    
    projects_str = ", ".join(filters.project_keys)
    jql_parts.append(f"project IN ({projects_str})")
    
    if filters.sprint_ids:
        sorted_sprint_ids = sorted(filters.sprint_ids)
        sprint_ids_str = ", ".join(str(sid) for sid in sorted_sprint_ids)
        jql_parts.append(f"sprint IN ({sprint_ids_str})")
    
    if filters.issue_types:
        sorted_types = sorted(filters.issue_types)
        types_str = ", ".join(f'"{t}"' for t in sorted_types)
        jql_parts.append(f"issuetype IN ({types_str})")
    
    if filters.date_range:
        use_updated = filters.date_mode == "created_or_updated"
        if filters.date_range.start and filters.date_range.end:
            start_str = filters.date_range.start.strftime("%Y-%m-%d")
            end_str = filters.date_range.end.strftime("%Y-%m-%d")
            if use_updated:
                jql_parts.append(
                    f"((created >= '{start_str}' AND created <= '{end_str}') "
                    f"OR (updated >= '{start_str}' AND updated <= '{end_str}'))"
                )
            else:
                jql_parts.append(f"created >= '{start_str}' AND created <= '{end_str}'")
        else:
            if filters.date_range.start:
                start_str = filters.date_range.start.strftime("%Y-%m-%d")
                if use_updated:
                    jql_parts.append(f"(created >= '{start_str}' OR updated >= '{start_str}')")
                else:
                    jql_parts.append(f"created >= '{start_str}'")
            if filters.date_range.end:
                end_str = filters.date_range.end.strftime("%Y-%m-%d")
                if use_updated:
                    jql_parts.append(f"(created <= '{end_str}' OR updated <= '{end_str}')")
                else:
                    jql_parts.append(f"created <= '{end_str}'")
    
    return " AND ".join(jql_parts)


def load_issues(connector: Optional[JiraConnector], filters: Filters) -> List[Issue]:
    """Load issues from Jira."""
    if not connector:
        return []
    
    # If no project selected, don't load issues (too many)
    if not filters.project_keys:
        return []
    
    # Check if INFRA project is selected (special JQL)
    is_infra_only = filters.project_keys == ["INFRA"]
    
    if is_infra_only:
        jql = _build_infra_jql(filters)
    else:
        jql = _build_default_jql(filters)
    
    import logging
    logging.getLogger(__name__).info(f"[load_issues] JQL: {jql}")
    st.toast(f"JQL: {jql}", icon="🔍")
    
    # Build date JQL fragment for board queries
    date_jql = ""
    if not is_infra_only and filters.date_range:
        use_updated = filters.date_mode == "created_or_updated"
        date_parts = []
        if filters.date_range.start and filters.date_range.end:
            s = filters.date_range.start.strftime("%Y-%m-%d")
            e = filters.date_range.end.strftime("%Y-%m-%d")
            if use_updated:
                date_parts.append(
                    f"((created >= '{s}' AND created <= '{e}') "
                    f"OR (updated >= '{s}' AND updated <= '{e}'))"
                )
            else:
                date_parts.append(f"created >= '{s}' AND created <= '{e}'")
        else:
            if filters.date_range.start:
                s = filters.date_range.start.strftime("%Y-%m-%d")
                if use_updated:
                    date_parts.append(f"(created >= '{s}' OR updated >= '{s}')")
                else:
                    date_parts.append(f"created >= '{s}'")
            if filters.date_range.end:
                e = filters.date_range.end.strftime("%Y-%m-%d")
                if use_updated:
                    date_parts.append(f"(created <= '{e}' OR updated <= '{e}')")
                else:
                    date_parts.append(f"created <= '{e}'")
        if date_parts:
            date_jql = " AND ".join(date_parts)
    
    # Cache key includes board strategy
    cache_key = f"issues_full_{hash(jql)}_boards"
    
    cached = CacheManager.get_cached_data(cache_key)
    if cached:
        return cached
    
    try:
        fields = ["summary", "status", "assignee", "issuetype", "created",
                 "updated", "resolutiondate", "labels", "components", 
                 "customfield_10370", "customfield_10016", "customfield_10026",
                 "customfield_11891",
                 "statuscategorychangedate"]
        
        all_issues = []
        seen_keys = set()
        
        # For non-INFRA projects, try fetching via boards to get cross-project issues
        if not is_infra_only:
            for proj_key in filters.project_keys:
                try:
                    boards = connector.get_boards(project_key=proj_key)
                    if boards:
                        for board in boards:
                            board_id = board["id"]
                            next_token = None
                            while True:
                                result = connector.get_board_issues(
                                    board_id, fields, jql_extra=date_jql or None, next_page_token=next_token
                                )
                                for issue in result.issues:
                                    if issue.key not in seen_keys:
                                        seen_keys.add(issue.key)
                                        all_issues.append(issue)
                                
                                is_last = getattr(result, 'is_last', True)
                                next_token = getattr(result, 'next_page_token', None)
                                if is_last or not next_token:
                                    break
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Board fetch failed for {proj_key}: {e}")
        
        # If no board issues found (or INFRA), fallback to JQL search
        if not all_issues:
            next_token = None
            while True:
                try:
                    result = connector.get_issues(jql, fields, next_page_token=next_token)
                except TypeError:
                    result = connector.get_issues(jql, fields, start_at=len(all_issues))
                for issue in result.issues:
                    if issue.key not in seen_keys:
                        seen_keys.add(issue.key)
                        all_issues.append(issue)
                
                is_last = getattr(result, 'is_last', True)
                next_token = getattr(result, 'next_page_token', None)
                if is_last or not next_token:
                    break
        
        # Post-fetch date filter to ensure no out-of-range issues
        if filters.date_range and all_issues:
            filtered = []
            for issue in all_issues:
                created = issue.created_date
                if filters.date_range.start and created:
                    from datetime import datetime
                    start_dt = datetime.combine(filters.date_range.start, datetime.min.time())
                    if created < start_dt:
                        continue
                if filters.date_range.end and created:
                    from datetime import datetime
                    end_dt = datetime.combine(filters.date_range.end, datetime.max.time())
                    if created > end_dt:
                        continue
                filtered.append(issue)
            all_issues = filtered
        
        CacheManager.set_cached_data(cache_key, all_issues)
        return all_issues
    except Exception as e:
        st.warning("⚠️ Erro ao carregar issues.")
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
    
    # Lead time: resolution_date - started_date
    lead_times = []
    for issue in done_issues:
        if issue.resolution_date and issue.started_date:
            delta = issue.resolution_date - issue.started_date
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
def _render_issue_type_pie(issues: List[Issue]):
    """Render pie chart with issue type distribution."""
    if not issues:
        return
    
    import plotly.express as px
    from collections import Counter
    
    st.subheader("📊 Percentual por Tipo de Issue")
    
    _excluded_types = {"Epic", "Épico", "Story", "História"}
    type_counts = Counter(i.issue_type for i in issues if i.issue_type and i.issue_type not in _excluded_types)
    
    fig = px.pie(
        values=list(type_counts.values()),
        names=list(type_counts.keys()),
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        margin=dict(t=20, b=20, l=20, r=20),
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig, use_container_width=True)


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
    
    # Group by type (exclude Epic and Story)
    _excluded_types = {"Epic", "Épico", "Story", "História"}
    flow_map: dict[str, dict[str, int]] = defaultdict(lambda: {"entradas": 0, "saidas": 0})
    
    for issue in issues:
        tipo = issue.issue_type or "Outros"
        if tipo in _excluded_types:
            continue
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
            width="stretch",
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


def _get_jira_base_url() -> str:
    """Get Jira base URL from session config."""
    _config = st.session_state.get("config")
    if _config and hasattr(_config, "jira") and hasattr(_config.jira, "base_url"):
        return _config.jira.base_url.rstrip("/")
    return ""


def _make_issue_link_column(df_data: list, key_field: str = "Key") -> tuple:
    """
    Convert issue keys to Jira links in a dataframe data list.
    Returns (modified_data, column_config) for st.dataframe.
    """
    base_url = _get_jira_base_url()
    if not base_url:
        return df_data, {}
    
    for row in df_data:
        if key_field in row:
            row[key_field] = f"{base_url}/browse/{row[key_field]}"
    
    col_config = {
        key_field: st.column_config.LinkColumn(key_field, display_text=r"https?://.+/browse/(.+)")
    }
    return df_data, col_config


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
    
    # OKRs
    from src.ui.okr_components import render_okrs_for_tab
    render_okrs_for_tab("project", {
        "overloaded_members": overloaded_count,
        "avg_allocation": avg_allocation,
    })
    
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
    
    # Pie chart: issue distribution by type
    st.divider()
    _render_issue_type_pie(issues)
    
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
    # Load teams for member lookup
    teams = load_teams()
    
    st.write("**Detalhamento por Membro** (clique para expandir)")
    
    for metric in allocation_metrics:
        # Status emoji and color
        status_emoji = {
            AllocationStatus.NORMAL: "✅",
            AllocationStatus.OVERLOADED: "🔴",
            AllocationStatus.UNDERUTILIZED: "🟡"
        }.get(metric.status, "⚪")
        
        # Find team for this member
        member_team = find_team_for_member(teams, metric.entity_name) or "Sem time"
        
        with st.expander(f"{status_emoji} {metric.entity_name} ({member_team}) - {metric.allocation_rate:.1f}%"):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Issues Atribuídas", metric.assigned_issues)
            with col2:
                st.metric("Esforço (horas)", f"{metric.total_story_points:.1f}h",
                         help="Baseado no T-Shirt Size das issues")
            with col3:
                st.metric("Status", metric.status.value.title())
            with col4:
                st.metric("Time", member_team)
            
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
                        "Criado": issue.created_date.strftime("%d/%m/%Y %H:%M") if issue.created_date else "-",
                        "Início": issue.started_date.strftime("%d/%m/%Y %H:%M") if issue.started_date else "-",
                        "Fim": issue.resolution_date.strftime("%d/%m/%Y %H:%M") if issue.resolution_date else "-"
                    })
                _data, _col_cfg = _make_issue_link_column(issue_data)
                st.dataframe(_data, width="stretch", hide_index=True, column_config=_col_cfg)


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
                 help="Tempo médio desde início até resolução")
    
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
    # Load teams for member lookup
    teams = load_teams()
    
    st.write("**Detalhamento de Produtividade** (clique para expandir)")
    
    with st.expander("📈 Throughput - Issues Concluídas", expanded=False):
        done_issues = [i for i in issues if i.status_category == "Done"]
        if done_issues:
            from src.models.data_models import get_tshirt_size_label
            issue_data = []
            for issue in done_issues:
                # Find team for assignee
                assignee_team = find_team_for_member(teams, issue.assignee_name) if issue.assignee_name else "Sem time"
                issue_data.append({
                    "Key": issue.key,
                    "Resumo": issue.summary[:40] + "..." if len(issue.summary) > 40 else issue.summary,
                    "Tipo": issue.issue_type,
                    "Tamanho": get_tshirt_size_label(issue.t_shirt_size),
                    "Responsável": issue.assignee_name or "N/A",
                    "Time": assignee_team or "Sem time",
                    "Criado": issue.created_date.strftime("%d/%m/%Y %H:%M") if issue.created_date else "-",
                    "Início": issue.started_date.strftime("%d/%m/%Y %H:%M") if issue.started_date else "-",
                    "Fim": issue.resolution_date.strftime("%d/%m/%Y %H:%M") if issue.resolution_date else "-"
                })
            _data2, _col_cfg2 = _make_issue_link_column(issue_data)
            st.dataframe(_data2, width="stretch", hide_index=True, column_config=_col_cfg2)
        else:
            st.info("Nenhuma issue concluída")
    
    with st.expander("⏱️ Lead Time - Detalhes", expanded=False):
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
    
    with st.expander("🔄 Cycle Time - Detalhes", expanded=False):
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
                "Criado": issue.created_date.strftime("%d/%m/%Y %H:%M") if issue.created_date else "N/A"
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
# Teams Configuration Page
# =============================================================================

def render_teams_page():
    """Render the teams configuration page."""
    from src.config.teams_loader import load_teams, save_teams, Team, TeamMember
    
    st.header("👥 Configuração de Times")
    st.markdown("Visualize e gerencie os times e seus membros.")
    
    st.divider()
    
    # Load teams
    teams = load_teams()
    
    if not teams:
        st.warning("Nenhum time configurado. O arquivo times.json não foi encontrado ou está vazio.")
        return
    
    # Summary
    total_members = sum(len(t.membros) + 1 for t in teams)  # +1 for tech leader
    unique_teams = len(set(t.time for t in teams))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Times", unique_teams)
    with col2:
        st.metric("Total de Membros", total_members)
    with col3:
        st.metric("Tech Leaders", len(teams))
    
    st.divider()
    
    # Search by professional
    search_query = st.text_input(
        "🔍 Buscar profissional",
        placeholder="Digite o nome do profissional...",
        key="teams_search_professional"
    )
    
    # If searching, show search results
    if search_query:
        search_lower = search_query.lower().strip()
        results = []
        
        for team in teams:
            # Check tech leader
            if search_lower in team.tech_leader.lower():
                results.append({
                    "Nome": team.tech_leader,
                    "Função": "Tech Leader",
                    "Time": team.time
                })
            
            # Check members
            for member in team.membros:
                if search_lower in member.nome.lower():
                    results.append({
                        "Nome": member.nome,
                        "Função": member.funcao,
                        "Time": team.time
                    })
        
        if results:
            st.success(f"✅ {len(results)} resultado(s) encontrado(s)")
            st.dataframe(
                results,
                width="stretch",
                hide_index=True,
                column_config={
                    "Nome": st.column_config.TextColumn("Nome", width="medium"),
                    "Função": st.column_config.TextColumn("Função", width="medium"),
                    "Time": st.column_config.TextColumn("Time", width="medium")
                }
            )
        else:
            st.warning(f"Nenhum profissional encontrado com '{search_query}'")
        
        st.divider()
    
    # Display teams
    for i, team in enumerate(teams):
        with st.expander(f"🏢 {team.time} - Tech Leader: {team.tech_leader}", expanded=False):
            # Team info
            col1, col2 = st.columns([1, 3])
            
            with col1:
                st.markdown(f"**Tech Leader:**")
                st.markdown(f"**Membros:**")
            
            with col2:
                st.markdown(f"{team.tech_leader}")
                st.markdown(f"{len(team.membros)} pessoas")
            
            # Members table
            if team.membros:
                st.markdown("---")
                st.markdown("**Equipe:**")
                
                member_data = []
                for member in team.membros:
                    member_data.append({
                        "Nome": member.nome,
                        "Função": member.funcao
                    })
                
                st.dataframe(
                    member_data,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Nome": st.column_config.TextColumn("Nome", width="medium"),
                        "Função": st.column_config.TextColumn("Função", width="medium")
                    }
                )
    
    st.divider()
    
    # Info about editing
    st.info(
        "💡 Para editar os times, modifique o arquivo `src/config/times.json` diretamente. "
        "As alterações serão refletidas após recarregar a página."
    )


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
        st.error("❌ Erro ao carregar projetos do Jira.")
        return
    
    if not project_keys:
        st.info("ℹ️ Nenhum projeto disponível.")
        return
    
    # Load teams for filter
    teams = load_teams()
    team_names = get_team_names(teams)
    
    # Filtros em linha única
    with st.expander("🔍 Filtros", expanded=True):
        col1, col2, col3, col4, col5 = st.columns([2.5, 1.5, 1.5, 1.5, 0.8])
        
        # Get date range from session state
        prof_start_date = st.session_state.get("prof_filter_start_date")
        prof_end_date = st.session_state.get("prof_filter_end_date")
        prof_selected_team = st.session_state.get("prof_filter_team", "")
        
        prof_date_range = None
        if prof_start_date or prof_end_date:
            prof_date_range = DateRange(
                start=prof_start_date,
                end=prof_end_date
            )
        
        # Load professionals with loading animation
        professionals = None
        with st.spinner("Carregando profissionais..."):
            try:
                professionals = get_all_professionals_cached(
                    connector=connector,
                    project_keys=project_keys,
                    default_capacity=default_capacity,
                    base_url=jira_base_url,
                    date_range=prof_date_range
                )
            except Exception as e:
                st.error("❌ Erro ao carregar profissionais.")
                return
        
        # Filter professionals by team if selected
        if prof_selected_team and professionals:
            from src.config.teams_loader import _normalize
            team_members = get_team_members_by_name(teams, prof_selected_team)
            team_members_norm = [_normalize(m) for m in team_members]
            
            filtered_professionals = []
            for prof in professionals:
                prof_name_norm = _normalize(prof.display_name)
                for member in team_members_norm:
                    if member in prof_name_norm or prof_name_norm in member:
                        filtered_professionals.append(prof)
                        break
            professionals = filtered_professionals
        
        with col1:
            if professionals:
                prof_options = {
                    p.account_id: f"{p.display_name} ({p.project_count} projeto{'s' if p.project_count != 1 else ''})"
                    for p in professionals
                }
                account_ids = [""] + list(prof_options.keys())
                
                selected_professional_id = st.selectbox(
                    "Profissional",
                    options=account_ids,
                    format_func=lambda x: "Selecione um profissional..." if not x else prof_options.get(x, x),
                    key="prof_filter_professional"
                )
            else:
                selected_professional_id = None
                st.info("Nenhum profissional disponível.")
        
        with col2:
            # Team filter
            team_options = [""] + team_names
            prof_selected_team = st.selectbox(
                "Time",
                options=team_options,
                format_func=lambda x: "Todos os times" if x == "" else x,
                key="prof_filter_team",
                help="Filtrar profissionais por time"
            )
        
        with col3:
            prof_start_date = st.date_input(
                "Data Início",
                value=None,
                key="prof_filter_start_date",
                help="Filtrar issues criadas a partir desta data"
            )
        
        with col4:
            prof_end_date = st.date_input(
                "Data Fim",
                value=None,
                key="prof_filter_end_date",
                help="Filtrar issues criadas até esta data"
            )
        
        with col5:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("🔄", key="refresh_professionals", help="Atualizar dados"):
                clear_professionals_cache()
                st.session_state.professionals_preload_started = False
                st.rerun()
    
    # Rebuild date range after inputs
    prof_date_range = None
    if prof_start_date or prof_end_date:
        prof_date_range = DateRange(
            start=prof_start_date,
            end=prof_end_date
        )
    
    # Show active filter info
    filter_parts = []
    if prof_selected_team:
        filter_parts.append(f"Time: {prof_selected_team}")
    if prof_start_date:
        filter_parts.append(f"De: {prof_start_date.strftime('%d/%m/%Y')}")
    if prof_end_date:
        filter_parts.append(f"Até: {prof_end_date.strftime('%d/%m/%Y')}")
    
    info_text = f"📁 {len(project_keys)} projetos | 👥 {len(professionals) if professionals else 0} profissionais"
    if filter_parts:
        info_text += f" | 🔍 {' - '.join(filter_parts)}"
    st.caption(info_text)
    
    # Instantiate ProfessionalMetricsEngine for rendering
    try:
        metrics_engine = ProfessionalMetricsEngine(
            connector=connector,
            cache=CacheManager,
            default_capacity=default_capacity,
            date_range=prof_date_range
        )
    except Exception as e:
        st.error("❌ Erro ao inicializar engine de métricas.")
        return
    
    # If team is selected, show all professionals from that team
    if prof_selected_team and professionals:
        st.subheader(f"👥 Time: {prof_selected_team}")
        st.caption(f"{len(professionals)} profissionais no time")
        
        # Render each professional in the team
        for idx, prof in enumerate(professionals):
            with st.expander(f"👤 {prof.display_name}", expanded=False):
                render_professional_view_content(
                    selected_professional_id=prof.account_id,
                    professionals=professionals,
                    metrics_engine=metrics_engine,
                    key_suffix=f"_team_{idx}"
                )
        return
    
    # Check if professional is selected (when no team filter)
    if not selected_professional_id:
        st.info("👆 Selecione um profissional ou um time no filtro acima para visualizar a alocação.")
        return
    
    # Render the professional view content (without the selector, which is now in filters)
    render_professional_view_content(
        selected_professional_id=selected_professional_id,
        professionals=professionals,
        metrics_engine=metrics_engine,
        key_suffix="_single"
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
    if filters.issue_types:
        filter_parts.append(f"Tipos: {', '.join(filters.issue_types)}")
    
    # Get selected teams from session state
    selected_teams = st.session_state.get("selected_teams", [])
    if selected_teams:
        filter_parts.append(f"Times: {', '.join(selected_teams)}")
    
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
    
    # Filter issues by team if teams are selected
    if selected_teams:
        from src.config.teams_loader import _normalize
        teams = load_teams()
        team_members = []
        for team_name in selected_teams:
            team_members.extend(get_team_members_by_name(teams, team_name))
        team_members_norm = [_normalize(m) for m in team_members]
        
        filtered_issues = []
        for issue in issues:
            if issue.assignee_name:
                assignee_norm = _normalize(issue.assignee_name)
                for member in team_members_norm:
                    if member in assignee_norm or assignee_norm in member:
                        filtered_issues.append(issue)
                        break
        issues = filtered_issues
    
    if not issues:
        st.warning(f"Nenhuma issue encontrada para os times selecionados.")
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
    
    # Load projects (cached) - sprints are loaded per-tab when needed
    if "cached_projects_list" not in st.session_state:
        with st.spinner("Carregando projetos..."):
            projects = load_projects(connector, config)
            st.session_state.cached_projects_list = projects
    else:
        projects = st.session_state.cached_projects_list
    sprints = []  # Sprints loaded on demand per tab
    
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
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div style="
                    background: {'rgba(34, 197, 94, 0.15)' if connection_status.connected else 'rgba(239, 68, 68, 0.15)'};
                    color: {'#22C55E' if connection_status.connected else '#EF4444'};
                    padding: 0.4rem 1rem;
                    border-radius: 20px;
                    font-size: 0.8rem;
                    font-weight: 500;
                ">{status_badge}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Logout button (small, top right)
    _cols_spacer, _col_logout = st.columns([0.94, 0.06])
    with _col_logout:
        if st.button("🚪 Sair", key="btn_logout", type="tertiary"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.session_state.logged_out = True
            st.rerun()
    
    # Main content area with tabs
    tab_cycle, tab_dashboard, tab_professional, tab_report, tab_teams = st.tabs([
        "🔄 Visão Unificada",
        "📊 Visão por Projeto",
        "👤 Visão por Profissional",
        "📄 Relatórios",
        "👥 Times",
    ])
    
    with tab_teams:
        render_teams_page()
    
    with tab_dashboard:
        if st.session_state.get("load_dashboard_tab", False):
            filters = render_inline_filters(projects, sprints)
            
            # Store current filter state to detect changes
            current_filter_key = f"{filters.project_keys}_{filters.sprint_ids}"
            if "last_dashboard_filter_key" not in st.session_state:
                st.session_state.last_dashboard_filter_key = None
            
            # Check if filters changed
            if st.session_state.last_dashboard_filter_key != current_filter_key:
                st.session_state.last_dashboard_filter_key = current_filter_key
            
            render_dashboard_content(filters, projects, sprints, connection_status)
        else:
            st.info("👆 Clique abaixo para carregar a visão por projeto.")
            if st.button("Carregar Visão por Projeto", key="btn_load_dash_tab", type="primary"):
                st.session_state.load_dashboard_tab = True
                st.rerun()
    
    with tab_professional:
        if st.session_state.get("load_professional_tab", False):
            render_professional_view_tab(connector, config, connection_status)
        else:
            st.info("👆 Clique abaixo para carregar a visão por profissional.")
            if st.button("Carregar Visão por Profissional", key="btn_load_prof_tab", type="primary"):
                st.session_state.load_professional_tab = True
                st.rerun()
    
    with tab_cycle:
        # Cycle view filters
        with st.expander("🔍 Filtros", expanded=True):
            cc1, cc2, cc3 = st.columns([2, 2, 2])
            
            with cc1:
                cycle_project_options = {p.key: f"{p.key} - {p.name}" for p in projects}
                cycle_selected_projects = st.multiselect(
                    "Projetos",
                    options=list(cycle_project_options.keys()),
                    format_func=lambda x: cycle_project_options.get(x, x),
                    key="cycle_filter_projects",
                    placeholder="Selecione os projetos"
                ) if cycle_project_options else []
            
            with cc2:
                cycle_start = st.date_input("Data Início", value=None, key="cycle_filter_start")
            
            with cc3:
                cycle_end = st.date_input("Data Fim", value=None, key="cycle_filter_end")
        
        if cycle_selected_projects:
            cycle_date_range = None
            if cycle_start or cycle_end:
                cycle_date_range = DateRange(start=cycle_start, end=cycle_end)
            
            cycle_filters = Filters(
                project_keys=cycle_selected_projects,
                date_range=cycle_date_range
            )
            cycle_issues = load_issues(connector, cycle_filters)
            render_cycle_view_tab(cycle_issues)
        else:
            st.info("👆 Selecione um projeto nos filtros acima para visualizar o ciclo completo.")
    
    with tab_report:
        # Load allowed projects list
        import os as _os
        from src.utils.crypto import load_encrypted_json
        _allowed_projects_path = _os.path.join(_os.path.dirname(__file__), "src", "config", "allowed_projects.json")
        _allowed_projects = load_encrypted_json(_allowed_projects_path) or []

        # All report filters together
        with st.expander("🔍 Filtros", expanded=True):
            rc1, rc2, rc3 = st.columns([2, 2, 2])
            
            with rc1:
                _tooltip_lines = "  \n".join(f"• {p['key']} - {p['name']}" for p in _allowed_projects)
                _tooltip = f"**Projetos liberados:**  \n{_tooltip_lines}" if _allowed_projects else ""
                report_project_options = {p.key: f"{p.key} - {p.name}" for p in projects}
                report_selected_projects = st.multiselect(
                    "Projetos",
                    options=list(report_project_options.keys()),
                    format_func=lambda x: report_project_options.get(x, x),
                    key="report_filter_projects",
                    placeholder="Selecione os projetos",
                    help=_tooltip
                ) if report_project_options else []
            
            with rc2:
                report_start = st.date_input("Data Início", value=None, key="report_filter_start")
            
            with rc3:
                report_end = st.date_input("Data Fim", value=None, key="report_filter_end")
            
            # Auto-load issue types when projects change
            report_proj_key = str(sorted(report_selected_projects)) if report_selected_projects else ""
            if report_proj_key and report_proj_key != st.session_state.get("report_last_proj_key", ""):
                st.session_state.report_last_proj_key = report_proj_key
                # Clear previous results when project changes
                st.session_state.pop("report_issues", None)
                st.session_state.pop("ai_analysis_result", None)
                # Quick fetch to populate filter options
                _report_date_range = None
                if report_start or report_end:
                    _report_date_range = DateRange(start=report_start, end=report_end)
                _quick_filters = Filters(project_keys=report_selected_projects, date_range=_report_date_range, date_mode="created")
                with st.spinner("Carregando opções de filtro..."):
                    _quick_issues = load_issues(connector, _quick_filters)
                if _quick_issues:
                    _teams = load_teams()
                    st.session_state.report_available_types = sorted(set(i.issue_type for i in _quick_issues if i.issue_type))
                    st.session_state.report_available_statuses = sorted(set(i.status for i in _quick_issues if i.status))
                    st.session_state.report_available_teams = sorted(set(
                        find_team_for_member(_teams, i.assignee_name) or "Sem time"
                        for i in _quick_issues if i.assignee_name
                    ))
                    st.session_state.report_issues = _quick_issues
                    st.rerun()
            elif not report_proj_key:
                st.session_state.report_last_proj_key = ""
                st.session_state.report_available_types = []
                st.session_state.report_available_statuses = []
                st.session_state.report_available_teams = []
                st.session_state.pop("report_issues", None)
                st.session_state.pop("ai_analysis_result", None)
            
            # Secondary filters row
            rc4, rc5, rc6, rc7, rc8 = st.columns([2, 2, 2, 1, 1])
            
            with rc4:
                report_type_filter = st.multiselect(
                    "Tipo de Issue",
                    options=st.session_state.get("report_available_types", []),
                    key="report_filter_type",
                    placeholder="Todos os tipos"
                )
            
            with rc5:
                report_status_filter = st.multiselect(
                    "Status",
                    options=st.session_state.get("report_available_statuses", []),
                    key="report_filter_status",
                    placeholder="Todos os status"
                )
            
            with rc6:
                report_team_filter = st.multiselect(
                    "Time",
                    options=st.session_state.get("report_available_teams", []),
                    key="report_filter_team",
                    placeholder="Todos os times"
                )
            
            with rc7:
                st.write("")
                st.write("")
                report_search = st.button("🔍 Consultar", key="btn_report_search", type="primary", width="stretch")
            
            with rc8:
                st.write("")
                st.write("")
                report_clear = st.button("🗑️ Limpar", key="btn_report_clear", width="stretch")
        
        # Handle clear button
        if report_clear:
            for k in ["report_issues", "report_last_proj_key", "report_available_types",
                       "report_available_statuses", "report_available_teams", "ai_analysis_result",
                       "ai_analysis_prompt"]:
                st.session_state.pop(k, None)
            st.rerun()
        
        # Detect filter changes and clear results
        _current_filter_sig = f"{report_type_filter}_{report_status_filter}_{report_team_filter}"
        if _current_filter_sig != st.session_state.get("report_filter_sig", ""):
            st.session_state.report_filter_sig = _current_filter_sig
            st.session_state.pop("ai_analysis_result", None)
        
        # Date validation
        _date_invalid = False
        if report_start and report_end and report_start > report_end:
            st.error("⚠️ A Data Início não pode ser superior à Data Fim.")
            _date_invalid = True
        
        # Reload data when Consultar is clicked (applies date filters)
        if report_search and report_selected_projects and not _date_invalid:
            st.session_state.pop("ai_analysis_result", None)
            report_date_range = None
            if report_start or report_end:
                report_date_range = DateRange(start=report_start, end=report_end)
            
            report_filters = Filters(
                project_keys=report_selected_projects,
                date_range=report_date_range,
                date_mode="created"
            )
            with st.spinner("Carregando issues..."):
                report_issues = load_issues(connector, report_filters)
            st.session_state.report_issues = report_issues
            
            # Update available filter options
            if report_issues:
                _teams = load_teams()
                st.session_state.report_available_types = sorted(set(i.issue_type for i in report_issues if i.issue_type))
                st.session_state.report_available_statuses = sorted(set(i.status for i in report_issues if i.status))
                st.session_state.report_available_teams = sorted(set(
                    find_team_for_member(_teams, i.assignee_name) or "Sem time"
                    for i in report_issues if i.assignee_name
                ))
                st.rerun()
        
        if "report_issues" in st.session_state and st.session_state.report_issues:
            render_report_tab(
                st.session_state.report_issues,
                type_filter=st.session_state.get("report_filter_type", []),
                status_filter=st.session_state.get("report_filter_status", []),
                team_filter=st.session_state.get("report_filter_team", []),
            )
        elif not report_selected_projects:
            st.info("👆 Selecione um projeto e clique em Consultar para gerar o relatório.")


def render_inline_filters(projects: List[Project], sprints: List[Sprint]) -> Filters:
    """
    Render inline filters at the top of the dashboard tab.
    
    Args:
        projects: Available projects
        sprints: Available sprints
        
    Returns:
        Filters object with selected values
    """
    # Load teams
    teams = load_teams()
    team_names = get_team_names(teams)
    
    with st.expander("🔍 Filtros", expanded=True):
        # First row: Project, Sprint, Team
        col1, col2, col3 = st.columns([2, 2, 2])
        
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
                selected_sprint_ids = st.multiselect(
                    "Sprints",
                    options=[],
                    key="inline_filter_sprints",
                    disabled=True,
                    help="Selecione um projeto primeiro",
                    placeholder="Selecione um projeto primeiro"
                )
            else:
                available_sprints = []
                if "connector" in st.session_state and st.session_state.connector:
                    from src.cache.cache_manager import CacheManager
                    
                    all_sprints = []
                    board_names = {}  # Map board_id -> board_name
                    for project_key in selected_projects:
                        boards = st.session_state.connector.get_boards(project_key)
                        for board in boards:
                            board_id = board.get("id")
                            board_name = board.get("name", "")
                            if board_id:
                                board_names[board_id] = board_name
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
                    
                    seen_ids = set()
                    unique_sprints = []
                    for sprint in all_sprints:
                        if sprint.jira_id not in seen_ids:
                            seen_ids.add(sprint.jira_id)
                            unique_sprints.append(sprint)
                    
                    state_order = {"active": 0, "future": 1, "closed": 2}
                    unique_sprints.sort(key=lambda s: (
                        state_order.get(s.state, 3),
                        -(s.start_date.timestamp() if s.start_date else 0)
                    ))
                    available_sprints = unique_sprints
                
                # Show board name in sprint label for clarity
                sprint_options = {}
                for s in available_sprints:
                    bname = board_names.get(s.board_id, "")
                    label = f"{s.name} ({s.state})"
                    if bname:
                        label = f"[{bname}] {s.name} ({s.state})"
                    sprint_options[s.jira_id] = label
                
                selected_sprint_ids = st.multiselect(
                    "Sprints",
                    options=list(sprint_options.keys()),
                    format_func=lambda x: sprint_options.get(x, str(x)),
                    key="inline_filter_sprints",
                    help=f"{len(available_sprints)} sprints disponíveis" if available_sprints else "Nenhum sprint encontrado",
                    placeholder="Selecione os sprints"
                )
        
        with col3:
            # Team filter
            selected_teams = st.multiselect(
                "Time",
                options=team_names,
                key="inline_filter_teams",
                help="Filtrar por time (deixe vazio para todos)",
                placeholder="Todos os times"
            )
        
        # Second row: Type, Date Start, Date End, Clear
        col4, col5, col6, col7 = st.columns([2, 1.5, 1.5, 0.8])
        
        with col4:
            issue_type_options = ["Bug", "Task", "Sub-task", "Story", "Improvement", "Epic"]
            selected_issue_types = st.multiselect(
                "Tipo de Item",
                options=issue_type_options,
                key="inline_filter_issue_types",
                help="Deixe vazio para todos os tipos",
                placeholder="Todos os tipos"
            )
        
        with col5:
            start_date = st.date_input(
                "Data Início",
                value=None,
                key="inline_filter_start_date",
                help="Filtrar issues criadas a partir desta data"
            )
        
        with col6:
            end_date = st.date_input(
                "Data Fim",
                value=None,
                key="inline_filter_end_date",
                help="Filtrar issues criadas até esta data"
            )
        
        with col7:
            st.write("")
            st.write("")
            if st.button("🗑️ Limpar", key="inline_clear_filters"):
                st.rerun()
    
    # Store selected teams in session state for filtering
    st.session_state.selected_teams = selected_teams
    
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
        assignees=[],
        issue_types=selected_issue_types,
        date_mode="created"
    )


if __name__ == "__main__":
    main()
