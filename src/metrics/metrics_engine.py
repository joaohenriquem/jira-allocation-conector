"""
Metrics Engine Module.

This module provides the MetricsEngine class for calculating allocation
and productivity metrics from Jira data.
"""

from typing import List, Literal, Optional
from dataclasses import dataclass, field

from ..models.data_models import (
    AllocationMetrics,
    AllocationStatus,
    DateRange,
    Issue,
    TeamMember,
)
from ..connector.jira_connector import JiraConnector


@dataclass
class TeamAllocation:
    """Aggregated team allocation metrics."""
    total_members: int
    total_story_points: float
    total_assigned_issues: int
    average_allocation_rate: float
    members_overloaded: int
    members_underutilized: int
    members_normal: int
    member_allocations: List[AllocationMetrics] = field(default_factory=list)


class MetricsEngine:
    """
    Engine for calculating allocation and productivity metrics.
    
    Provides methods to calculate:
    - Allocation rate per member
    - Team allocation (aggregated)
    - Workload distribution
    - Throughput, lead time, cycle time
    - Velocity and sprint completion rate
    """
    
    # Thresholds for allocation status classification
    OVERLOADED_THRESHOLD = 100.0  # >100% = overloaded
    UNDERUTILIZED_THRESHOLD = 50.0  # <50% = underutilized
    
    # Default capacity in story points per sprint
    DEFAULT_CAPACITY = 40.0
    
    def __init__(self, connector: JiraConnector):
        """
        Initialize engine with connector.
        
        Args:
            connector: JiraConnector instance for fetching data
        """
        self.connector = connector
        self._member_capacities: dict[str, float] = {}
    
    def set_member_capacity(self, member_id: str, capacity: float) -> None:
        """
        Set capacity for a specific member.
        
        Args:
            member_id: Member's Jira account ID
            capacity: Capacity in story points
        """
        self._member_capacities[member_id] = capacity
    
    def get_member_capacity(self, member_id: str) -> float:
        """
        Get capacity for a member, returning default if not set.
        
        Args:
            member_id: Member's Jira account ID
            
        Returns:
            Capacity in story points
        """
        return self._member_capacities.get(member_id, self.DEFAULT_CAPACITY)
    
    def calculate_allocation_rate(
        self,
        member_id: str,
        period: DateRange,
        issues: Optional[List[Issue]] = None
    ) -> float:
        """
        Calculate allocation rate for a member (0-100+).
        
        Formula: (story_points / capacity) * 100
        
        Args:
            member_id: Member's Jira account ID
            period: Date range for calculation
            issues: Optional pre-fetched issues (if None, would need to fetch)
            
        Returns:
            Allocation rate as percentage (0-100+)
        """
        if issues is None:
            return 0.0
        
        # Filter issues assigned to this member
        member_issues = [
            issue for issue in issues
            if issue.assignee_account_id == member_id
        ]
        
        # Sum story points (treat None as 0)
        total_story_points = sum(
            issue.story_points or 0.0
            for issue in member_issues
        )
        
        # Get member capacity
        capacity = self.get_member_capacity(member_id)
        
        # Calculate allocation rate
        if capacity <= 0:
            return 0.0
        
        return (total_story_points / capacity) * 100
    
    def calculate_team_allocation(
        self,
        team_members: List[str],
        period: DateRange,
        issues: Optional[List[Issue]] = None
    ) -> TeamAllocation:
        """
        Calculate aggregated team allocation.
        
        Args:
            team_members: List of member Jira account IDs
            period: Date range for calculation
            issues: Optional pre-fetched issues
            
        Returns:
            TeamAllocation with aggregated metrics
        """
        if issues is None:
            issues = []
        
        member_allocations: List[AllocationMetrics] = []
        total_story_points = 0.0
        total_assigned_issues = 0
        members_overloaded = 0
        members_underutilized = 0
        members_normal = 0
        
        for member_id in team_members:
            # Filter issues for this member
            member_issues = [
                issue for issue in issues
                if issue.assignee_account_id == member_id
            ]
            
            # Calculate story points
            story_points = sum(
                issue.story_points or 0.0
                for issue in member_issues
            )
            
            # Calculate allocation rate
            allocation_rate = self.calculate_allocation_rate(
                member_id, period, issues
            )
            
            # Classify status
            status = self.classify_allocation_status(allocation_rate)
            
            # Count by status
            if status == "overloaded":
                members_overloaded += 1
                alloc_status = AllocationStatus.OVERLOADED
            elif status == "underutilized":
                members_underutilized += 1
                alloc_status = AllocationStatus.UNDERUTILIZED
            else:
                members_normal += 1
                alloc_status = AllocationStatus.NORMAL
            
            # Get member name from issues if available
            member_name = member_id
            for issue in member_issues:
                if issue.assignee_name:
                    member_name = issue.assignee_name
                    break
            
            allocation = AllocationMetrics(
                entity_id=member_id,
                entity_name=member_name,
                allocation_rate=allocation_rate,
                assigned_issues=len(member_issues),
                total_story_points=story_points,
                status=alloc_status
            )
            member_allocations.append(allocation)
            
            total_story_points += story_points
            total_assigned_issues += len(member_issues)
        
        # Calculate average allocation rate
        if team_members:
            average_allocation_rate = sum(
                m.allocation_rate for m in member_allocations
            ) / len(team_members)
        else:
            average_allocation_rate = 0.0
        
        return TeamAllocation(
            total_members=len(team_members),
            total_story_points=total_story_points,
            total_assigned_issues=total_assigned_issues,
            average_allocation_rate=average_allocation_rate,
            members_overloaded=members_overloaded,
            members_underutilized=members_underutilized,
            members_normal=members_normal,
            member_allocations=member_allocations
        )
    
    def calculate_workload_distribution(
        self,
        team_members: List[str],
        period: DateRange,
        issues: Optional[List[Issue]] = None
    ) -> dict[str, float]:
        """
        Calculate workload distribution percentages (sum = 100%).
        
        Args:
            team_members: List of member Jira account IDs
            period: Date range for calculation
            issues: Optional pre-fetched issues
            
        Returns:
            Dictionary mapping member_id to percentage of total workload
        """
        if issues is None:
            issues = []
        
        # Calculate story points per member
        member_points: dict[str, float] = {}
        total_points = 0.0
        
        for member_id in team_members:
            member_issues = [
                issue for issue in issues
                if issue.assignee_account_id == member_id
            ]
            points = sum(
                issue.story_points or 0.0
                for issue in member_issues
            )
            member_points[member_id] = points
            total_points += points
        
        # Calculate percentages
        distribution: dict[str, float] = {}
        
        if total_points > 0:
            for member_id in team_members:
                distribution[member_id] = (
                    member_points[member_id] / total_points
                ) * 100
        else:
            # Equal distribution when no work assigned
            if team_members:
                equal_share = 100.0 / len(team_members)
                for member_id in team_members:
                    distribution[member_id] = equal_share
        
        return distribution
    
    def classify_allocation_status(
        self,
        allocation_rate: float
    ) -> Literal["normal", "overloaded", "underutilized"]:
        """
        Classify allocation status based on thresholds.
        
        - >100% = overloaded
        - <50% = underutilized
        - 50-100% = normal
        
        Args:
            allocation_rate: Allocation rate percentage
            
        Returns:
            Status classification string
        """
        if allocation_rate > self.OVERLOADED_THRESHOLD:
            return "overloaded"
        elif allocation_rate < self.UNDERUTILIZED_THRESHOLD:
            return "underutilized"
        else:
            return "normal"
    
    def calculate_throughput(self, issues: List[Issue]) -> int:
        """
        Calculate throughput (count of completed issues).
        
        Args:
            issues: List of issues to analyze
            
        Returns:
            Count of issues with status_category = "Done"
        """
        return sum(
            1 for issue in issues
            if issue.status_category == "Done"
        )
    
    def calculate_lead_time(self, issues: List[Issue]) -> Optional[float]:
        """
        Calculate average lead time in hours.
        
        Lead time = resolution_date - started_date
        
        Args:
            issues: List of issues to analyze
            
        Returns:
            Average lead time in hours, or None if no valid data
        """
        lead_times: List[float] = []
        
        for issue in issues:
            if issue.resolution_date and issue.started_date:
                delta = issue.resolution_date - issue.started_date
                hours = delta.total_seconds() / 3600
                if hours >= 0:  # Only positive lead times
                    lead_times.append(hours)
        
        if not lead_times:
            return None
        
        return sum(lead_times) / len(lead_times)
    
    def calculate_cycle_time(self, issues: List[Issue]) -> Optional[float]:
        """
        Calculate average cycle time in hours.
        
        Cycle time = resolution_date - started_date
        
        Args:
            issues: List of issues to analyze
            
        Returns:
            Average cycle time in hours, or None if no valid data
        """
        cycle_times: List[float] = []
        
        for issue in issues:
            if issue.resolution_date and issue.started_date:
                delta = issue.resolution_date - issue.started_date
                hours = delta.total_seconds() / 3600
                if hours >= 0:  # Only positive cycle times
                    cycle_times.append(hours)
        
        if not cycle_times:
            return None
        
        return sum(cycle_times) / len(cycle_times)
    
    def calculate_velocity(self, issues: List[Issue]) -> float:
        """
        Calculate velocity (sum of story points for completed issues).
        
        Args:
            issues: List of issues to analyze
            
        Returns:
            Sum of story points for issues with status_category = "Done"
        """
        return sum(
            issue.story_points or 0.0
            for issue in issues
            if issue.status_category == "Done"
        )
    
    def calculate_sprint_completion_rate(
        self,
        planned: int,
        completed: int
    ) -> Optional[float]:
        """
        Calculate sprint completion rate.
        
        Formula: (completed / planned) * 100
        
        Args:
            planned: Number of planned issues
            completed: Number of completed issues
            
        Returns:
            Completion rate as percentage, or None if planned is 0
        """
        if planned <= 0:
            return None
        
        return (completed / planned) * 100
