"""
Professional Metrics Engine Module.

This module provides the ProfessionalMetricsEngine class for calculating
cross-project allocation metrics for individual professionals.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional

from ..cache.cache_manager import CacheManager
from ..connector.jira_connector import JiraConnector
from ..models.data_models import (
    AllocationStatus,
    DateRange,
    Issue,
    Professional,
    ProfessionalAllocation,
    ProjectAllocation,
    WeeklyAllocation,
)


class ProfessionalMetricsEngine:
    """
    Engine for calculating cross-project allocation metrics for professionals.
    
    Provides methods to:
    - Extract unique professionals from issues across projects
    - Calculate consolidated allocation across all projects
    - Generate timeline of weekly allocations
    - Cache results for performance optimization
    """
    
    # Default capacity in story points per sprint
    DEFAULT_CAPACITY = 24.0
    
    # Cache TTL in seconds (1 hour)
    CACHE_TTL_SECONDS = 3600
    
    # Default timeline period in weeks
    DEFAULT_TIMELINE_WEEKS = 8
    
    # Thresholds for allocation status classification
    OVERLOADED_THRESHOLD = 100.0  # >100% = overloaded
    UNDERUTILIZED_THRESHOLD = 50.0  # <50% = underutilized
    
    def __init__(
        self,
        connector: JiraConnector,
        cache: CacheManager,
        default_capacity: float = DEFAULT_CAPACITY,
        upper_threshold: float = OVERLOADED_THRESHOLD,
        lower_threshold: float = UNDERUTILIZED_THRESHOLD,
        date_range: Optional["DateRange"] = None
    ):
        """
        Initialize engine with connector and cache.
        
        Args:
            connector: JiraConnector instance for fetching data
            cache: CacheManager instance for caching results
            default_capacity: Default capacity in story points per sprint
            upper_threshold: Upper threshold for overloaded status
            lower_threshold: Lower threshold for underutilized status
            date_range: Optional date range filter for issues
        """
        self.connector = connector
        self.cache = cache
        self._default_capacity = default_capacity
        self._upper_threshold = upper_threshold
        self._lower_threshold = lower_threshold
        self._professional_capacities: Dict[str, float] = {}
        self._last_load_stats: Dict[str, int] = {}
        self._date_range = date_range

    def set_professional_capacity(self, professional_id: str, capacity: float) -> None:
        """
        Set capacity for a specific professional.
        
        Args:
            professional_id: Professional's Jira account ID
            capacity: Capacity in story points
        """
        self._professional_capacities[professional_id] = capacity
    
    def _get_professional_capacity(self, professional_id: str) -> float:
        """
        Get capacity for a professional, returning default if not set.
        
        Args:
            professional_id: Professional's Jira account ID
            
        Returns:
            Capacity in story points
        """
        return self._professional_capacities.get(professional_id, self._default_capacity)
    
    def _classify_status(self, allocation_rate: float) -> AllocationStatus:
        """
        Classify allocation status based on thresholds.
        
        - allocation_rate > upper_threshold → OVERLOADED
        - allocation_rate < lower_threshold → UNDERUTILIZED
        - otherwise → NORMAL
        
        Args:
            allocation_rate: Allocation rate percentage
            
        Returns:
            AllocationStatus enum value
        """
        if allocation_rate > self._upper_threshold:
            return AllocationStatus.OVERLOADED
        elif allocation_rate < self._lower_threshold:
            return AllocationStatus.UNDERUTILIZED
        else:
            return AllocationStatus.NORMAL
    
    def _generate_cache_key(
        self,
        prefix: str,
        professional_id: Optional[str] = None,
        sprint_ids: Optional[List[int]] = None,
        project_keys: Optional[List[str]] = None
    ) -> str:
        """
        Generate a unique cache key for the given parameters.
        
        Args:
            prefix: Cache key prefix
            professional_id: Optional professional ID
            sprint_ids: Optional list of sprint IDs
            project_keys: Optional list of project keys
            
        Returns:
            Unique cache key string
        """
        parts = [prefix]
        
        if professional_id:
            parts.append(professional_id)
        
        if sprint_ids:
            sorted_sprints = sorted(sprint_ids)
            parts.append(f"sprints_{hash(tuple(sorted_sprints))}")
        
        if project_keys:
            sorted_keys = sorted(project_keys)
            parts.append(f"projects_{hash(tuple(sorted_keys))}")
        
        return "_".join(parts)

    def _fetch_all_issues_for_projects(
        self,
        project_keys: List[str],
        sprint_ids: Optional[List[int]] = None
    ) -> List[Issue]:
        """
        Fetch all issues from the specified projects.
        
        Args:
            project_keys: List of project keys to fetch issues from
            sprint_ids: Optional list of sprint IDs to filter by
            
        Returns:
            List of Issue objects
        """
        if not project_keys:
            return []
        
        all_issues: List[Issue] = []
        fields = [
            "summary", "status", "assignee", "issuetype",
            "customfield_10370", "customfield_10016", "customfield_10026",
            "customfield_11891",
            "labels", "components", "created", "resolutiondate",
            "statuscategorychangedate"
        ]
        
        # Fetch issues for each project separately to avoid JQL length limits
        for project_key in project_keys:
            jql = f'project = "{project_key}"'
            
            if sprint_ids:
                sprint_clause = ", ".join(str(s) for s in sprint_ids)
                jql += f" AND sprint IN ({sprint_clause})"
            
            # Add filter to only get issues with assignee (optimization)
            jql += " AND assignee IS NOT EMPTY"
            
            # Add date range filter if specified
            if self._date_range:
                if self._date_range.start:
                    start_str = self._date_range.start.strftime("%Y-%m-%d")
                    jql += f" AND created >= '{start_str}'"
                if self._date_range.end:
                    end_str = self._date_range.end.strftime("%Y-%m-%d")
                    jql += f" AND created <= '{end_str}'"
            
            next_token = None
            while True:
                try:
                    result = self.connector.get_issues(jql, fields, next_page_token=next_token)
                    all_issues.extend(result.issues)
                    
                    is_last = getattr(result, 'is_last', True)
                    next_token = getattr(result, 'next_page_token', None)
                    
                    if is_last or not next_token:
                        break
                except Exception:
                    # Skip projects that fail (e.g., no permission)
                    break
        
        return all_issues
    
    def _fetch_issues_for_professional(
        self,
        professional_id: str,
        sprint_ids: Optional[List[int]] = None
    ) -> List[Issue]:
        """
        Fetch all issues assigned to a specific professional.
        
        Args:
            professional_id: Professional's Jira account ID
            sprint_ids: Optional list of sprint IDs to filter by
            
        Returns:
            List of Issue objects
        """
        # Build JQL query
        jql = f'assignee = "{professional_id}"'
        
        if sprint_ids:
            sprint_clause = ", ".join(str(s) for s in sprint_ids)
            jql += f" AND sprint IN ({sprint_clause})"
        
        # Add date range filter if specified
        if self._date_range:
            if self._date_range.start:
                start_str = self._date_range.start.strftime("%Y-%m-%d")
                jql += f" AND created >= '{start_str}'"
            if self._date_range.end:
                end_str = self._date_range.end.strftime("%Y-%m-%d")
                jql += f" AND created <= '{end_str}'"
        
        # Fetch all issues with pagination
        all_issues: List[Issue] = []
        fields = [
            "summary", "status", "assignee", "issuetype",
            "customfield_10370", "customfield_10016", "customfield_10026",
            "customfield_11891",
            "labels", "components", "created", "resolutiondate",
            "statuscategorychangedate"
        ]
        
        next_token = None
        while True:
            result = self.connector.get_issues(jql, fields, next_page_token=next_token)
            all_issues.extend(result.issues)
            
            is_last = getattr(result, 'is_last', True)
            next_token = getattr(result, 'next_page_token', None)
            
            if is_last or not next_token:
                break
        
        return all_issues

    def get_all_professionals(
        self,
        project_keys: List[str]
    ) -> List[Professional]:
        """
        Extract unique professionals from issues in the specified projects.
        
        Uses cache to avoid repeated API calls. Extracts unique assignees
        from all issues and returns them as Professional objects.
        
        Args:
            project_keys: List of project keys to extract professionals from
            
        Returns:
            List of Professional objects with unique account_ids
        """
        if not project_keys:
            return []
        
        # Check cache first
        cache_key = self._generate_cache_key("professionals_list", project_keys=project_keys)
        cached_data = self.cache.get_cached_data(cache_key)
        if cached_data is not None:
            return cached_data
        
        # Fetch all issues from projects (no sprint filter to get all professionals)
        all_issues = self._fetch_all_issues_for_projects(project_keys, sprint_ids=None)
        
        # Extract unique professionals
        professionals_dict: Dict[str, Professional] = {}
        project_counts: Dict[str, set] = {}  # account_id -> set of project_keys
        issues_with_assignee = 0
        
        for issue in all_issues:
            if issue.assignee_account_id and issue.assignee_name:
                issues_with_assignee += 1
                account_id = issue.assignee_account_id
                
                # Track projects for this professional
                if account_id not in project_counts:
                    project_counts[account_id] = set()
                
                # Extract project key from issue key (e.g., "PROJ-123" -> "PROJ")
                project_key = issue.key.split("-")[0]
                project_counts[account_id].add(project_key)
                
                # Create or update professional
                if account_id not in professionals_dict:
                    professionals_dict[account_id] = Professional(
                        account_id=account_id,
                        display_name=issue.assignee_name,
                        project_count=0
                    )
        
        # Update project counts
        for account_id, projects in project_counts.items():
            if account_id in professionals_dict:
                professionals_dict[account_id].project_count = len(projects)
        
        # Convert to list and sort by display_name
        professionals = sorted(
            professionals_dict.values(),
            key=lambda p: p.display_name.lower()
        )
        
        # Store loading stats for debugging (can be accessed via engine._last_load_stats)
        self._last_load_stats = {
            "total_issues": len(all_issues),
            "issues_with_assignee": issues_with_assignee,
            "unique_professionals": len(professionals),
            "projects_searched": len(project_keys)
        }
        
        # Cache the result
        self.cache.set_cached_data(cache_key, professionals, self.CACHE_TTL_SECONDS)
        
        return professionals

    def _get_project_name(self, project_key: str) -> str:
        """
        Get project name from project key.
        
        Args:
            project_key: Project key (e.g., "PROJ")
            
        Returns:
            Project name or key if not found
        """
        try:
            projects = self.connector.get_projects([project_key])
            if projects:
                return projects[0].name
        except Exception:
            pass
        return project_key
    
    def _get_professional_name(
        self,
        professional_id: str,
        issues: List[Issue]
    ) -> str:
        """
        Get professional name from issues.
        
        Args:
            professional_id: Professional's Jira account ID
            issues: List of issues to search for name
            
        Returns:
            Professional name or ID if not found
        """
        for issue in issues:
            if issue.assignee_account_id == professional_id and issue.assignee_name:
                return issue.assignee_name
        return professional_id
    
    def calculate_cross_project_allocation(
        self,
        professional_id: str,
        sprint_ids: Optional[List[int]] = None
    ) -> ProfessionalAllocation:
        """
        Calculate consolidated allocation for a professional across all projects.
        
        Aggregates issues from all projects where the professional is assigned,
        calculates total story points, allocation rate, and generates a breakdown
        by project.
        
        Postconditions:
        - total_story_points == sum(project.story_points for project in breakdown)
        - total_issues == sum(project.issue_count for project in breakdown)
        - project_breakdown is sorted by story_points descending
        
        Args:
            professional_id: Professional's Jira account ID
            sprint_ids: Optional list of sprint IDs to filter by
            
        Returns:
            ProfessionalAllocation with consolidated metrics
        """
        # Check cache first
        cache_key = self._generate_cache_key(
            "prof_alloc",
            professional_id=professional_id,
            sprint_ids=sprint_ids
        )
        cached_data = self.cache.get_cached_data(cache_key)
        if cached_data is not None:
            return cached_data
        
        # Fetch all issues for this professional
        all_issues = self._fetch_issues_for_professional(professional_id, sprint_ids)
        
        # Group issues by project
        issues_by_project: Dict[str, List[Issue]] = {}
        for issue in all_issues:
            project_key = issue.key.split("-")[0]
            if project_key not in issues_by_project:
                issues_by_project[project_key] = []
            issues_by_project[project_key].append(issue)
        
        # Calculate metrics per project
        project_breakdown: List[ProjectAllocation] = []
        total_sp = 0.0
        total_issues = 0
        
        for project_key, issues in issues_by_project.items():
            sp = sum(i.story_points or 0.0 for i in issues)
            project_breakdown.append(ProjectAllocation(
                project_key=project_key,
                project_name=self._get_project_name(project_key),
                story_points=sp,
                issue_count=len(issues),
                allocation_percentage=0.0,  # Calculated after total is known
                issues=issues
            ))
            total_sp += sp
            total_issues += len(issues)
        
        # Calculate allocation percentages
        if total_sp > 0:
            for proj in project_breakdown:
                proj.allocation_percentage = (proj.story_points / total_sp) * 100
        
        # Sort by story_points descending
        project_breakdown.sort(key=lambda p: p.story_points, reverse=True)
        
        # Calculate total allocation rate
        capacity = self._get_professional_capacity(professional_id)
        allocation_rate = (total_sp / capacity) * 100 if capacity > 0 else 0.0
        
        # Classify status
        status = self._classify_status(allocation_rate)
        
        # Get professional name
        professional_name = self._get_professional_name(professional_id, all_issues)
        
        # Build result
        result = ProfessionalAllocation(
            professional_id=professional_id,
            professional_name=professional_name,
            total_allocation_rate=allocation_rate,
            total_story_points=total_sp,
            total_issues=total_issues,
            project_breakdown=project_breakdown,
            status=status,
            capacity=capacity
        )
        
        # Cache the result
        self.cache.set_cached_data(cache_key, result, self.CACHE_TTL_SECONDS)
        
        return result

    def get_professional_timeline(
        self,
        professional_id: str,
        weeks: int = DEFAULT_TIMELINE_WEEKS
    ) -> List[WeeklyAllocation]:
        """
        Generate timeline of weekly allocations for a professional.
        
        Calculates allocation for each week in the specified period,
        including breakdown by project.
        
        Args:
            professional_id: Professional's Jira account ID
            weeks: Number of weeks to include (default: 8)
            
        Returns:
            List of WeeklyAllocation objects, one per week
        """
        if weeks <= 0:
            weeks = self.DEFAULT_TIMELINE_WEEKS
        
        # Check cache first
        cache_key = self._generate_cache_key(
            f"prof_timeline_{weeks}w",
            professional_id=professional_id
        )
        cached_data = self.cache.get_cached_data(cache_key)
        if cached_data is not None:
            return cached_data
        
        # Calculate date range
        today = date.today()
        # Start from the beginning of the current week (Monday)
        days_since_monday = today.weekday()
        current_week_start = today - timedelta(days=days_since_monday)
        
        # Go back (weeks - 1) weeks to get the start of the timeline
        timeline_start = current_week_start - timedelta(weeks=weeks - 1)
        
        # Fetch all issues for this professional (without sprint filter for timeline)
        all_issues = self._fetch_issues_for_professional(professional_id)
        
        # Get professional capacity
        capacity = self._get_professional_capacity(professional_id)
        
        # Generate weekly allocations
        timeline: List[WeeklyAllocation] = []
        
        for week_offset in range(weeks):
            week_start = timeline_start + timedelta(weeks=week_offset)
            week_end = week_start + timedelta(days=6)
            
            # Filter issues that were active during this week
            # An issue is considered active if it was created before week_end
            # and either not resolved or resolved after week_start
            week_issues: List[Issue] = []
            for issue in all_issues:
                issue_created = issue.created_date.date() if issue.created_date else None
                issue_resolved = issue.resolution_date.date() if issue.resolution_date else None
                
                # Issue must be created before or during this week
                if issue_created and issue_created > week_end:
                    continue
                
                # If resolved, must be resolved during or after this week
                if issue_resolved and issue_resolved < week_start:
                    continue
                
                week_issues.append(issue)
            
            # Calculate story points and breakdown for this week
            project_breakdown: Dict[str, float] = {}
            total_sp = 0.0
            
            for issue in week_issues:
                project_key = issue.key.split("-")[0]
                sp = issue.story_points or 0.0
                
                if project_key not in project_breakdown:
                    project_breakdown[project_key] = 0.0
                project_breakdown[project_key] += sp
                total_sp += sp
            
            # Calculate allocation rate for this week
            allocation_rate = (total_sp / capacity) * 100 if capacity > 0 else 0.0
            
            timeline.append(WeeklyAllocation(
                week_start=week_start,
                week_end=week_end,
                total_story_points=total_sp,
                allocation_rate=allocation_rate,
                project_breakdown=project_breakdown
            ))
        
        # Cache the result
        self.cache.set_cached_data(cache_key, timeline, self.CACHE_TTL_SECONDS)
        
        return timeline
