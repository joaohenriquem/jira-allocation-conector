"""
Data models for Jira Allocation Connector.

This module contains all dataclasses and enums used throughout the application
for representing Jira data, metrics, configuration, and AI assistant models.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self


# =============================================================================
# T-Shirt Size Enum and Mapping (Task: Replace Story Points)
# =============================================================================

class TShirtSize(Enum):
    """T-Shirt Size classification for issue complexity."""
    PP = "PP"      # XS - Muito simples (1-4 horas)
    P = "P"        # S - Simples (0.5-1 dia)
    M = "M"        # M - Moderada (1-3 dias)
    G = "G"        # L - Complexa (3-5 dias)
    GG = "GG"      # XL - Muito complexa (1-2 semanas)
    XGG = "XGG"    # XXL - Gigante (2+ semanas)


# Mapeamento de T-Shirt Size para valor numérico (em horas estimadas)
TSHIRT_SIZE_VALUES = {
    TShirtSize.PP: 2.5,    # 1-4 horas -> média 2.5h
    TShirtSize.P: 6.0,     # 0.5-1 dia -> média 6h
    TShirtSize.M: 16.0,    # 1-3 dias -> média 2 dias = 16h
    TShirtSize.G: 32.0,    # 3-5 dias -> média 4 dias = 32h
    TShirtSize.GG: 60.0,   # 1-2 semanas -> média 1.5 semanas = 60h
    TShirtSize.XGG: 100.0, # 2+ semanas -> média 2.5 semanas = 100h
}

# Mapeamento de string para enum (suporta variações)
TSHIRT_SIZE_MAP = {
    # Padrão PP/P/M/G/GG/XGG
    "PP": TShirtSize.PP,
    "P": TShirtSize.P,
    "M": TShirtSize.M,
    "G": TShirtSize.G,
    "GG": TShirtSize.GG,
    "XGG": TShirtSize.XGG,
    # Variações XS/S/M/L/XL/XXL
    "XS": TShirtSize.PP,
    "S": TShirtSize.P,
    "L": TShirtSize.G,
    "XL": TShirtSize.GG,
    "XXL": TShirtSize.XGG,
    # Variações com parênteses
    "PP (XS)": TShirtSize.PP,
    "P (S)": TShirtSize.P,
    "G (L)": TShirtSize.G,
    "GG (XL)": TShirtSize.GG,
    "XGG (XXL)": TShirtSize.XGG,
}


def get_tshirt_size_value(size: Optional[str]) -> float:
    """
    Converte T-Shirt Size string para valor numérico em horas.
    
    Args:
        size: String do tamanho (PP, P, M, G, GG, XGG ou variações)
        
    Returns:
        Valor em horas estimadas, ou 0.0 se não reconhecido
    """
    if not size:
        return 0.0
    
    size_upper = size.upper().strip()
    tshirt_enum = TSHIRT_SIZE_MAP.get(size_upper)
    
    if tshirt_enum:
        return TSHIRT_SIZE_VALUES[tshirt_enum]
    
    return 0.0


def get_tshirt_size_label(size: Optional[str]) -> str:
    """
    Retorna label descritivo para o T-Shirt Size.
    
    Args:
        size: String do tamanho
        
    Returns:
        Label descritivo com tempo estimado
    """
    labels = {
        "PP": "PP (1-4h)",
        "P": "P (0.5-1 dia)",
        "M": "M (1-3 dias)",
        "G": "G (3-5 dias)",
        "GG": "GG (1-2 sem)",
        "XGG": "XGG (2+ sem)",
    }
    
    if not size:
        return "Não definido"
    
    size_upper = size.upper().strip()
    tshirt_enum = TSHIRT_SIZE_MAP.get(size_upper)
    
    if tshirt_enum:
        return labels.get(tshirt_enum.value, size)
    
    return size


# =============================================================================
# Configuration Models (Task 2.2)
# =============================================================================

@dataclass
class JiraConfig:
    """Configuration for Jira API connection."""
    base_url: str
    auth_type: Literal["api_token", "pat"]
    username: Optional[str] = None
    api_token: Optional[str] = None
    personal_access_token: Optional[str] = None


@dataclass
class AppConfig:
    """Application configuration."""
    jira: JiraConfig
    cache_ttl_seconds: int = 900
    projects: List[str] = field(default_factory=list)
    default_capacity_hours: float = 40.0


@dataclass
class ConnectionStatus:
    """Status of connection to Jira server."""
    connected: bool
    server_info: Optional[dict] = None
    error_message: Optional[str] = None
    last_checked: datetime = field(default_factory=datetime.now)
    is_stale: bool = False  # True when using cached data after connection failure


@dataclass
class AuthResult:
    """Result of authentication attempt."""
    success: bool
    user_info: Optional[dict] = None
    error_message: Optional[str] = None


# =============================================================================
# Jira Entity Models (Task 2.3)
# =============================================================================

@dataclass
class Project:
    """Jira project representation."""
    jira_id: str
    key: str
    name: str
    description: Optional[str] = None
    lead_account_id: Optional[str] = None


@dataclass
class Sprint:
    """Jira sprint representation."""
    jira_id: int
    name: str
    state: Literal["future", "active", "closed"]
    board_id: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    complete_date: Optional[datetime] = None
    goal: Optional[str] = None


@dataclass
class Issue:
    """Jira issue representation."""
    jira_id: str
    key: str
    summary: str
    issue_type: str
    status: str
    status_category: Literal["To Do", "In Progress", "Done"]
    assignee_account_id: Optional[str] = None
    assignee_name: Optional[str] = None
    t_shirt_size: Optional[str] = None  # T-Shirt Size (PP, P, M, G, GG, XGG)
    story_points: Optional[float] = None  # Calculado a partir do T-Shirt Size
    labels: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)
    created_date: datetime = field(default_factory=datetime.now)
    resolution_date: Optional[datetime] = None
    started_date: Optional[datetime] = None
    
    def __post_init__(self):
        """Calcula story_points a partir do t_shirt_size se não definido."""
        if self.t_shirt_size and self.story_points is None:
            self.story_points = get_tshirt_size_value(self.t_shirt_size)


@dataclass
class TeamMember:
    """Team member representation."""
    jira_account_id: str
    display_name: str
    email: Optional[str] = None
    capacity_hours_per_sprint: float = 40.0


# =============================================================================
# Metrics Models (Task 2.4)
# =============================================================================

class AllocationStatus(Enum):
    """Status classification for allocation metrics."""
    NORMAL = "Normal"
    OVERLOADED = "Sobrecarregado"
    UNDERUTILIZED = "Subutilizado"


@dataclass
class AllocationMetrics:
    """Allocation metrics for a team member or entity."""
    entity_id: str
    entity_name: str
    allocation_rate: float  # Percentage 0-100+
    assigned_issues: int
    total_story_points: float
    status: AllocationStatus


@dataclass
class ProductivityMetrics:
    """Productivity metrics for a team or project."""
    throughput: int
    lead_time_avg_hours: Optional[float] = None
    cycle_time_avg_hours: Optional[float] = None
    velocity: Optional[float] = None
    completion_rate: Optional[float] = None


# =============================================================================
# Professional Allocation Models
# =============================================================================

@dataclass
class Professional:
    """Representação de um profissional.
    
    Attributes:
        account_id: ID único da conta do profissional no Jira
        display_name: Nome de exibição do profissional
        email: Email do profissional (opcional)
        avatar_url: URL do avatar do profissional (opcional)
        project_count: Número de projetos em que está alocado
    """
    account_id: str
    display_name: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    project_count: int = 0
    
    def __post_init__(self) -> None:
        """Valida os campos obrigatórios após inicialização."""
        if not self.account_id or not self.account_id.strip():
            raise ValueError("account_id não pode ser vazio")
        if not self.display_name or not self.display_name.strip():
            raise ValueError("display_name não pode ser vazio")


@dataclass
class ProjectAllocation:
    """Alocação do profissional em um projeto específico.
    
    Attributes:
        project_key: Chave do projeto no Jira (ex: PROJ)
        project_name: Nome do projeto
        story_points: Total de story points atribuídos ao profissional neste projeto
        issue_count: Número de issues atribuídas ao profissional neste projeto
        allocation_percentage: Percentual do total do profissional alocado neste projeto (0-100)
        issues: Lista de issues atribuídas ao profissional neste projeto
    """
    project_key: str
    project_name: str
    story_points: float
    issue_count: int
    allocation_percentage: float
    issues: List['Issue'] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Valida os campos após inicialização."""
        if self.story_points < 0:
            raise ValueError("story_points deve ser >= 0")
        if self.issue_count < 0:
            raise ValueError("issue_count deve ser >= 0")
        if not (0 <= self.allocation_percentage <= 100):
            raise ValueError("allocation_percentage deve estar entre 0 e 100")


@dataclass
class ProfessionalAllocation:
    """Alocação consolidada cross-project de um profissional.
    
    Attributes:
        professional_id: ID da conta do profissional no Jira
        professional_name: Nome de exibição do profissional
        total_allocation_rate: Taxa de alocação total (0-100+%)
        total_story_points: Total de story points em todos os projetos
        total_issues: Total de issues em todos os projetos
        project_breakdown: Lista de alocações por projeto
        status: Status de alocação (Normal, Sobrecarregado, Subutilizado)
        capacity: Capacidade configurada do profissional
        period_start: Data de início do período analisado (opcional)
        period_end: Data de fim do período analisado (opcional)
    """
    professional_id: str
    professional_name: str
    total_allocation_rate: float
    total_story_points: float
    total_issues: int
    project_breakdown: List[ProjectAllocation]
    status: AllocationStatus
    capacity: float
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    
    def __post_init__(self) -> None:
        """Valida os campos após inicialização."""
        if self.total_allocation_rate < 0:
            raise ValueError("total_allocation_rate deve ser >= 0")
        if self.capacity <= 0:
            raise ValueError("capacity deve ser > 0")


@dataclass
class WeeklyAllocation:
    """Alocação semanal para timeline.
    
    Attributes:
        week_start: Data de início da semana
        week_end: Data de fim da semana
        total_story_points: Total de story points na semana
        allocation_rate: Taxa de alocação na semana
        project_breakdown: Distribuição de story points por projeto (project_key -> story_points)
    """
    week_start: date
    week_end: date
    total_story_points: float
    allocation_rate: float
    project_breakdown: Dict[str, float] = field(default_factory=dict)


# =============================================================================
# Filter and Utility Models (Task 2.5)
# =============================================================================

@dataclass
class DateRange:
    """Date range for filtering."""
    start: date
    end: date


@dataclass
class Filters:
    """Filter criteria for queries."""
    project_keys: List[str] = field(default_factory=list)
    sprint_ids: List[int] = field(default_factory=list)
    date_range: Optional[DateRange] = None
    assignees: List[str] = field(default_factory=list)


@dataclass
class MetricTrend:
    """Trend data point for a metric."""
    date: date
    value: float
    metric_type: str


@dataclass
class CacheEntry:
    """Cache entry with expiration tracking."""
    data: Any
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# AI Assistant Models
# =============================================================================

class SuggestionPriority(Enum):
    """Priority level for AI suggestions."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SuggestionCategory(Enum):
    """Category for AI suggestions."""
    ALLOCATION = "allocation"
    PRODUCTIVITY = "productivity"
    RISK = "risk"
    PROCESS = "process"
    TEAM = "team"


@dataclass
class AISuggestion:
    """AI-generated suggestion."""
    title: str
    description: str
    priority: SuggestionPriority
    category: SuggestionCategory
    action_items: List[str] = field(default_factory=list)
    data_basis: str = ""  # Explanation of data that supports the suggestion


@dataclass
class AIConfig:
    """Configuration for AI assistant."""
    enabled: bool = False
    api_key: Optional[str] = None
    model: str = "gpt-4"
    provider: Literal["openai", "anthropic"] = "openai"
