"""
Unit tests for MetricsEngine.

Tests cover:
- calculate_allocation_rate()
- calculate_workload_distribution() sums to 100%
- classify_allocation_status() thresholds
- calculate_throughput()
- calculate_lead_time() and calculate_cycle_time()
- calculate_velocity()
- calculate_sprint_completion_rate()
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.metrics.metrics_engine import MetricsEngine, TeamAllocation
from src.models.data_models import (
    AllocationMetrics,
    AllocationStatus,
    DateRange,
    Issue,
    JiraConfig,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_connector():
    """Create a mock JiraConnector."""
    config = JiraConfig(
        base_url="https://test.atlassian.net",
        auth_type="pat",
        personal_access_token="test-token"
    )
    connector = MagicMock()
    connector.config = config
    return connector


@pytest.fixture
def metrics_engine(mock_connector):
    """Create a MetricsEngine instance with mock connector."""
    return MetricsEngine(mock_connector)


@pytest.fixture
def sample_date_range():
    """Create a sample date range for testing."""
    from datetime import date
    return DateRange(
        start=date(2024, 1, 1),
        end=date(2024, 1, 31)
    )


@pytest.fixture
def sample_issues():
    """Create sample issues for testing."""
    now = datetime.now()
    return [
        Issue(
            jira_id="1",
            key="PROJ-1",
            summary="Issue 1",
            issue_type="Story",
            status="Done",
            status_category="Done",
            assignee_account_id="user-1",
            assignee_name="User One",
            story_points=5.0,
            created_date=now - timedelta(days=10),
            resolution_date=now - timedelta(days=2),
            started_date=now - timedelta(days=7)
        ),
        Issue(
            jira_id="2",
            key="PROJ-2",
            summary="Issue 2",
            issue_type="Story",
            status="Done",
            status_category="Done",
            assignee_account_id="user-1",
            assignee_name="User One",
            story_points=3.0,
            created_date=now - timedelta(days=8),
            resolution_date=now - timedelta(days=1),
            started_date=now - timedelta(days=5)
        ),
        Issue(
            jira_id="3",
            key="PROJ-3",
            summary="Issue 3",
            issue_type="Bug",
            status="In Progress",
            status_category="In Progress",
            assignee_account_id="user-2",
            assignee_name="User Two",
            story_points=2.0,
            created_date=now - timedelta(days=5)
        ),
        Issue(
            jira_id="4",
            key="PROJ-4",
            summary="Issue 4",
            issue_type="Story",
            status="Done",
            status_category="Done",
            assignee_account_id="user-2",
            assignee_name="User Two",
            story_points=8.0,
            created_date=now - timedelta(days=15),
            resolution_date=now - timedelta(days=3),
            started_date=now - timedelta(days=10)
        ),
    ]


# =============================================================================
# Allocation Rate Tests
# =============================================================================

class TestCalculateAllocationRate:
    """Tests for calculate_allocation_rate() method."""

    def test_allocation_rate_basic_calculation(self, metrics_engine, sample_date_range, sample_issues):
        """Test basic allocation rate calculation."""
        # User-1 has 5 + 3 = 8 story points, default capacity is 40
        rate = metrics_engine.calculate_allocation_rate(
            member_id="user-1",
            period=sample_date_range,
            issues=sample_issues
        )
        
        # (8 / 40) * 100 = 20%
        assert rate == 20.0

    def test_allocation_rate_with_custom_capacity(self, metrics_engine, sample_date_range, sample_issues):
        """Test allocation rate with custom member capacity."""
        metrics_engine.set_member_capacity("user-1", 10.0)
        
        rate = metrics_engine.calculate_allocation_rate(
            member_id="user-1",
            period=sample_date_range,
            issues=sample_issues
        )
        
        # (8 / 10) * 100 = 80%
        assert rate == 80.0

    def test_allocation_rate_no_issues(self, metrics_engine, sample_date_range):
        """Test allocation rate when member has no issues."""
        rate = metrics_engine.calculate_allocation_rate(
            member_id="user-1",
            period=sample_date_range,
            issues=[]
        )
        
        assert rate == 0.0

    def test_allocation_rate_none_issues(self, metrics_engine, sample_date_range):
        """Test allocation rate when issues is None."""
        rate = metrics_engine.calculate_allocation_rate(
            member_id="user-1",
            period=sample_date_range,
            issues=None
        )
        
        assert rate == 0.0

    def test_allocation_rate_issues_without_story_points(self, metrics_engine, sample_date_range):
        """Test allocation rate when issues have no story points."""
        issues = [
            Issue(
                jira_id="1",
                key="PROJ-1",
                summary="Issue without points",
                issue_type="Story",
                status="Open",
                status_category="To Do",
                assignee_account_id="user-1",
                story_points=None
            )
        ]
        
        rate = metrics_engine.calculate_allocation_rate(
            member_id="user-1",
            period=sample_date_range,
            issues=issues
        )
        
        assert rate == 0.0

    def test_allocation_rate_overloaded(self, metrics_engine, sample_date_range):
        """Test allocation rate exceeding 100%."""
        metrics_engine.set_member_capacity("user-1", 5.0)
        
        issues = [
            Issue(
                jira_id="1",
                key="PROJ-1",
                summary="Big issue",
                issue_type="Story",
                status="Open",
                status_category="To Do",
                assignee_account_id="user-1",
                story_points=10.0
            )
        ]
        
        rate = metrics_engine.calculate_allocation_rate(
            member_id="user-1",
            period=sample_date_range,
            issues=issues
        )
        
        # (10 / 5) * 100 = 200%
        assert rate == 200.0


# =============================================================================
# Workload Distribution Tests
# =============================================================================

class TestCalculateWorkloadDistribution:
    """Tests for calculate_workload_distribution() method."""

    def test_workload_distribution_sums_to_100(self, metrics_engine, sample_date_range, sample_issues):
        """Test that workload distribution percentages sum to 100%."""
        distribution = metrics_engine.calculate_workload_distribution(
            team_members=["user-1", "user-2"],
            period=sample_date_range,
            issues=sample_issues
        )
        
        total = sum(distribution.values())
        assert abs(total - 100.0) < 0.01  # Allow small floating point error

    def test_workload_distribution_correct_percentages(self, metrics_engine, sample_date_range, sample_issues):
        """Test that workload distribution calculates correct percentages."""
        # user-1: 8 points, user-2: 10 points, total: 18 points
        distribution = metrics_engine.calculate_workload_distribution(
            team_members=["user-1", "user-2"],
            period=sample_date_range,
            issues=sample_issues
        )
        
        # user-1: (8/18) * 100 ≈ 44.44%
        # user-2: (10/18) * 100 ≈ 55.56%
        assert abs(distribution["user-1"] - 44.44) < 0.1
        assert abs(distribution["user-2"] - 55.56) < 0.1

    def test_workload_distribution_no_work(self, metrics_engine, sample_date_range):
        """Test workload distribution when no work is assigned."""
        distribution = metrics_engine.calculate_workload_distribution(
            team_members=["user-1", "user-2"],
            period=sample_date_range,
            issues=[]
        )
        
        # Equal distribution when no work
        assert distribution["user-1"] == 50.0
        assert distribution["user-2"] == 50.0

    def test_workload_distribution_single_member(self, metrics_engine, sample_date_range, sample_issues):
        """Test workload distribution with single team member."""
        distribution = metrics_engine.calculate_workload_distribution(
            team_members=["user-1"],
            period=sample_date_range,
            issues=sample_issues
        )
        
        assert distribution["user-1"] == 100.0

    def test_workload_distribution_empty_team(self, metrics_engine, sample_date_range, sample_issues):
        """Test workload distribution with empty team."""
        distribution = metrics_engine.calculate_workload_distribution(
            team_members=[],
            period=sample_date_range,
            issues=sample_issues
        )
        
        assert distribution == {}


# =============================================================================
# Allocation Status Classification Tests
# =============================================================================

class TestClassifyAllocationStatus:
    """Tests for classify_allocation_status() method."""

    def test_classify_normal_status(self, metrics_engine):
        """Test classification of normal allocation (50-100%)."""
        assert metrics_engine.classify_allocation_status(50.0) == "normal"
        assert metrics_engine.classify_allocation_status(75.0) == "normal"
        assert metrics_engine.classify_allocation_status(100.0) == "normal"

    def test_classify_overloaded_status(self, metrics_engine):
        """Test classification of overloaded allocation (>100%)."""
        assert metrics_engine.classify_allocation_status(100.1) == "overloaded"
        assert metrics_engine.classify_allocation_status(150.0) == "overloaded"
        assert metrics_engine.classify_allocation_status(200.0) == "overloaded"

    def test_classify_underutilized_status(self, metrics_engine):
        """Test classification of underutilized allocation (<50%)."""
        assert metrics_engine.classify_allocation_status(0.0) == "underutilized"
        assert metrics_engine.classify_allocation_status(25.0) == "underutilized"
        assert metrics_engine.classify_allocation_status(49.9) == "underutilized"

    def test_classify_boundary_values(self, metrics_engine):
        """Test classification at exact boundary values."""
        # Exactly 50% is normal (not underutilized)
        assert metrics_engine.classify_allocation_status(50.0) == "normal"
        
        # Exactly 100% is normal (not overloaded)
        assert metrics_engine.classify_allocation_status(100.0) == "normal"


# =============================================================================
# Throughput Tests
# =============================================================================

class TestCalculateThroughput:
    """Tests for calculate_throughput() method."""

    def test_throughput_counts_done_issues(self, metrics_engine, sample_issues):
        """Test that throughput counts only Done issues."""
        throughput = metrics_engine.calculate_throughput(sample_issues)
        
        # 3 issues with status_category = "Done"
        assert throughput == 3

    def test_throughput_empty_list(self, metrics_engine):
        """Test throughput with empty issue list."""
        throughput = metrics_engine.calculate_throughput([])
        assert throughput == 0

    def test_throughput_no_done_issues(self, metrics_engine):
        """Test throughput when no issues are done."""
        issues = [
            Issue(
                jira_id="1",
                key="PROJ-1",
                summary="In Progress Issue",
                issue_type="Story",
                status="In Progress",
                status_category="In Progress"
            ),
            Issue(
                jira_id="2",
                key="PROJ-2",
                summary="To Do Issue",
                issue_type="Story",
                status="Open",
                status_category="To Do"
            )
        ]
        
        throughput = metrics_engine.calculate_throughput(issues)
        assert throughput == 0

    def test_throughput_all_done(self, metrics_engine):
        """Test throughput when all issues are done."""
        issues = [
            Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Done Issue {i}",
                issue_type="Story",
                status="Done",
                status_category="Done"
            )
            for i in range(5)
        ]
        
        throughput = metrics_engine.calculate_throughput(issues)
        assert throughput == 5


# =============================================================================
# Lead Time Tests
# =============================================================================

class TestCalculateLeadTime:
    """Tests for calculate_lead_time() method."""

    def test_lead_time_calculation(self, metrics_engine, sample_issues):
        """Test lead time calculation (resolution - created)."""
        lead_time = metrics_engine.calculate_lead_time(sample_issues)
        
        # Should return average lead time in hours
        assert lead_time is not None
        assert lead_time > 0

    def test_lead_time_no_resolved_issues(self, metrics_engine):
        """Test lead time when no issues have resolution date."""
        issues = [
            Issue(
                jira_id="1",
                key="PROJ-1",
                summary="Unresolved Issue",
                issue_type="Story",
                status="Open",
                status_category="To Do",
                created_date=datetime.now() - timedelta(days=5)
            )
        ]
        
        lead_time = metrics_engine.calculate_lead_time(issues)
        assert lead_time is None

    def test_lead_time_empty_list(self, metrics_engine):
        """Test lead time with empty issue list."""
        lead_time = metrics_engine.calculate_lead_time([])
        assert lead_time is None

    def test_lead_time_single_issue(self, metrics_engine):
        """Test lead time with single resolved issue."""
        now = datetime.now()
        issues = [
            Issue(
                jira_id="1",
                key="PROJ-1",
                summary="Resolved Issue",
                issue_type="Story",
                status="Done",
                status_category="Done",
                created_date=now - timedelta(hours=48),
                resolution_date=now
            )
        ]
        
        lead_time = metrics_engine.calculate_lead_time(issues)
        
        # Should be approximately 48 hours
        assert lead_time is not None
        assert abs(lead_time - 48.0) < 1.0  # Allow 1 hour tolerance


# =============================================================================
# Cycle Time Tests
# =============================================================================

class TestCalculateCycleTime:
    """Tests for calculate_cycle_time() method."""

    def test_cycle_time_calculation(self, metrics_engine, sample_issues):
        """Test cycle time calculation (resolution - started)."""
        cycle_time = metrics_engine.calculate_cycle_time(sample_issues)
        
        # Should return average cycle time in hours
        assert cycle_time is not None
        assert cycle_time > 0

    def test_cycle_time_no_started_issues(self, metrics_engine):
        """Test cycle time when no issues have started date."""
        issues = [
            Issue(
                jira_id="1",
                key="PROJ-1",
                summary="Issue without started date",
                issue_type="Story",
                status="Done",
                status_category="Done",
                created_date=datetime.now() - timedelta(days=5),
                resolution_date=datetime.now()
            )
        ]
        
        cycle_time = metrics_engine.calculate_cycle_time(issues)
        assert cycle_time is None

    def test_cycle_time_empty_list(self, metrics_engine):
        """Test cycle time with empty issue list."""
        cycle_time = metrics_engine.calculate_cycle_time([])
        assert cycle_time is None

    def test_cycle_time_single_issue(self, metrics_engine):
        """Test cycle time with single issue."""
        now = datetime.now()
        issues = [
            Issue(
                jira_id="1",
                key="PROJ-1",
                summary="Completed Issue",
                issue_type="Story",
                status="Done",
                status_category="Done",
                created_date=now - timedelta(hours=72),
                started_date=now - timedelta(hours=24),
                resolution_date=now
            )
        ]
        
        cycle_time = metrics_engine.calculate_cycle_time(issues)
        
        # Should be approximately 24 hours
        assert cycle_time is not None
        assert abs(cycle_time - 24.0) < 1.0  # Allow 1 hour tolerance


# =============================================================================
# Velocity Tests
# =============================================================================

class TestCalculateVelocity:
    """Tests for calculate_velocity() method."""

    def test_velocity_sums_done_story_points(self, metrics_engine, sample_issues):
        """Test that velocity sums story points of Done issues."""
        velocity = metrics_engine.calculate_velocity(sample_issues)
        
        # Done issues: 5 + 3 + 8 = 16 story points
        assert velocity == 16.0

    def test_velocity_empty_list(self, metrics_engine):
        """Test velocity with empty issue list."""
        velocity = metrics_engine.calculate_velocity([])
        assert velocity == 0.0

    def test_velocity_no_done_issues(self, metrics_engine):
        """Test velocity when no issues are done."""
        issues = [
            Issue(
                jira_id="1",
                key="PROJ-1",
                summary="In Progress",
                issue_type="Story",
                status="In Progress",
                status_category="In Progress",
                story_points=10.0
            )
        ]
        
        velocity = metrics_engine.calculate_velocity(issues)
        assert velocity == 0.0

    def test_velocity_ignores_none_story_points(self, metrics_engine):
        """Test that velocity treats None story points as 0."""
        issues = [
            Issue(
                jira_id="1",
                key="PROJ-1",
                summary="Done without points",
                issue_type="Story",
                status="Done",
                status_category="Done",
                story_points=None
            ),
            Issue(
                jira_id="2",
                key="PROJ-2",
                summary="Done with points",
                issue_type="Story",
                status="Done",
                status_category="Done",
                story_points=5.0
            )
        ]
        
        velocity = metrics_engine.calculate_velocity(issues)
        assert velocity == 5.0


# =============================================================================
# Sprint Completion Rate Tests
# =============================================================================

class TestCalculateSprintCompletionRate:
    """Tests for calculate_sprint_completion_rate() method."""

    def test_completion_rate_basic(self, metrics_engine):
        """Test basic completion rate calculation."""
        rate = metrics_engine.calculate_sprint_completion_rate(planned=10, completed=8)
        
        # (8 / 10) * 100 = 80%
        assert rate == 80.0

    def test_completion_rate_100_percent(self, metrics_engine):
        """Test 100% completion rate."""
        rate = metrics_engine.calculate_sprint_completion_rate(planned=10, completed=10)
        assert rate == 100.0

    def test_completion_rate_0_percent(self, metrics_engine):
        """Test 0% completion rate."""
        rate = metrics_engine.calculate_sprint_completion_rate(planned=10, completed=0)
        assert rate == 0.0

    def test_completion_rate_over_100_percent(self, metrics_engine):
        """Test completion rate over 100% (more completed than planned)."""
        rate = metrics_engine.calculate_sprint_completion_rate(planned=10, completed=12)
        
        # (12 / 10) * 100 = 120%
        assert rate == 120.0

    def test_completion_rate_zero_planned(self, metrics_engine):
        """Test completion rate when no issues were planned."""
        rate = metrics_engine.calculate_sprint_completion_rate(planned=0, completed=5)
        assert rate is None

    def test_completion_rate_negative_planned(self, metrics_engine):
        """Test completion rate with negative planned (edge case)."""
        rate = metrics_engine.calculate_sprint_completion_rate(planned=-5, completed=3)
        assert rate is None


# =============================================================================
# Team Allocation Tests
# =============================================================================

class TestCalculateTeamAllocation:
    """Tests for calculate_team_allocation() method."""

    def test_team_allocation_aggregates_correctly(self, metrics_engine, sample_date_range, sample_issues):
        """Test that team allocation aggregates member metrics correctly."""
        result = metrics_engine.calculate_team_allocation(
            team_members=["user-1", "user-2"],
            period=sample_date_range,
            issues=sample_issues
        )
        
        assert isinstance(result, TeamAllocation)
        assert result.total_members == 2
        assert result.total_story_points == 18.0  # 8 + 10
        assert result.total_assigned_issues == 4

    def test_team_allocation_classifies_members(self, metrics_engine, sample_date_range):
        """Test that team allocation classifies members by status."""
        # Create issues that result in different allocation statuses
        issues = [
            Issue(
                jira_id="1",
                key="PROJ-1",
                summary="Overloaded user issue",
                issue_type="Story",
                status="Open",
                status_category="To Do",
                assignee_account_id="overloaded-user",
                story_points=50.0  # 125% of default 40 capacity
            ),
            Issue(
                jira_id="2",
                key="PROJ-2",
                summary="Underutilized user issue",
                issue_type="Story",
                status="Open",
                status_category="To Do",
                assignee_account_id="underutilized-user",
                story_points=10.0  # 25% of default 40 capacity
            ),
            Issue(
                jira_id="3",
                key="PROJ-3",
                summary="Normal user issue",
                issue_type="Story",
                status="Open",
                status_category="To Do",
                assignee_account_id="normal-user",
                story_points=30.0  # 75% of default 40 capacity
            )
        ]
        
        result = metrics_engine.calculate_team_allocation(
            team_members=["overloaded-user", "underutilized-user", "normal-user"],
            period=sample_date_range,
            issues=issues
        )
        
        assert result.members_overloaded == 1
        assert result.members_underutilized == 1
        assert result.members_normal == 1

    def test_team_allocation_empty_team(self, metrics_engine, sample_date_range, sample_issues):
        """Test team allocation with empty team."""
        result = metrics_engine.calculate_team_allocation(
            team_members=[],
            period=sample_date_range,
            issues=sample_issues
        )
        
        assert result.total_members == 0
        assert result.average_allocation_rate == 0.0


# =============================================================================
# Member Capacity Tests
# =============================================================================

class TestMemberCapacity:
    """Tests for member capacity management."""

    def test_set_and_get_member_capacity(self, metrics_engine):
        """Test setting and getting member capacity."""
        metrics_engine.set_member_capacity("user-1", 60.0)
        
        capacity = metrics_engine.get_member_capacity("user-1")
        assert capacity == 60.0

    def test_get_default_capacity(self, metrics_engine):
        """Test getting default capacity for unknown member."""
        capacity = metrics_engine.get_member_capacity("unknown-user")
        assert capacity == MetricsEngine.DEFAULT_CAPACITY

    def test_override_member_capacity(self, metrics_engine):
        """Test overriding member capacity."""
        metrics_engine.set_member_capacity("user-1", 50.0)
        metrics_engine.set_member_capacity("user-1", 80.0)
        
        capacity = metrics_engine.get_member_capacity("user-1")
        assert capacity == 80.0
