"""
Tests for ProfessionalMetricsEngine.

This module contains unit tests and property-based tests using the hypothesis library
to validate correctness properties from the design document.

Tests cover:
- Property 2: Consistência de Agregação de Alocação
- Property 3: Cálculo Correto da Taxa de Alocação
- Property 6: Ordenação do Breakdown por Story Points
- Property 7: Classificação Correta de Status de Alocação
- Property 10: Validação de Modelos de Dados
"""

from datetime import date, datetime, timedelta
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck

from src.cache.cache_manager import CacheManager
from src.metrics.professional_metrics import ProfessionalMetricsEngine
from src.models.data_models import (
    AllocationStatus,
    Issue,
    Professional,
    ProfessionalAllocation,
    ProjectAllocation,
    WeeklyAllocation,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_connector():
    """Create a mock JiraConnector."""
    connector = MagicMock()
    connector.get_projects.return_value = []
    return connector


@pytest.fixture
def mock_cache():
    """Create a mock CacheManager."""
    cache = MagicMock(spec=CacheManager)
    cache.get_cached_data.return_value = None
    return cache


@pytest.fixture
def metrics_engine(mock_connector, mock_cache):
    """Create a ProfessionalMetricsEngine instance with mocks."""
    return ProfessionalMetricsEngine(mock_connector, mock_cache)


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Strategy for generating valid story points (non-negative floats)
story_points_strategy = st.floats(
    min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False
)

# Strategy for generating valid capacity (positive floats)
capacity_strategy = st.floats(
    min_value=0.1, max_value=200.0, allow_nan=False, allow_infinity=False
)

# Strategy for generating allocation rates
allocation_rate_strategy = st.floats(
    min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False
)

# Strategy for generating non-empty strings for IDs and names
non_empty_string_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_'),
    min_size=1,
    max_size=20
)

# Strategy for generating project keys
project_key_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu',)),
    min_size=2,
    max_size=6
)


def create_issue(
    jira_id: str,
    project_key: str,
    assignee_id: str,
    story_points: float = None
) -> Issue:
    """Helper to create an Issue object."""
    return Issue(
        jira_id=jira_id,
        key=f"{project_key}-{jira_id}",
        summary=f"Issue {jira_id}",
        issue_type="Story",
        status="Open",
        status_category="To Do",
        assignee_account_id=assignee_id,
        assignee_name=f"User {assignee_id}",
        story_points=story_points,
        created_date=datetime.now() - timedelta(days=5)
    )


# =============================================================================
# Unit Tests - Task 5.1
# =============================================================================

class TestProfessionalMetricsEngineUnit:
    """Unit tests for ProfessionalMetricsEngine."""

    def test_classify_status_overloaded(self, metrics_engine):
        """Test status classification for overloaded allocation."""
        status = metrics_engine._classify_status(150.0)
        assert status == AllocationStatus.OVERLOADED

    def test_classify_status_underutilized(self, metrics_engine):
        """Test status classification for underutilized allocation."""
        status = metrics_engine._classify_status(30.0)
        assert status == AllocationStatus.UNDERUTILIZED

    def test_classify_status_normal(self, metrics_engine):
        """Test status classification for normal allocation."""
        status = metrics_engine._classify_status(75.0)
        assert status == AllocationStatus.NORMAL

    def test_classify_status_boundary_upper(self, metrics_engine):
        """Test status classification at upper boundary (100%)."""
        status = metrics_engine._classify_status(100.0)
        assert status == AllocationStatus.NORMAL

    def test_classify_status_boundary_lower(self, metrics_engine):
        """Test status classification at lower boundary (50%)."""
        status = metrics_engine._classify_status(50.0)
        assert status == AllocationStatus.NORMAL

    def test_get_professional_capacity_default(self, metrics_engine):
        """Test getting default capacity for unknown professional."""
        capacity = metrics_engine._get_professional_capacity("unknown-user")
        assert capacity == ProfessionalMetricsEngine.DEFAULT_CAPACITY

    def test_set_and_get_professional_capacity(self, metrics_engine):
        """Test setting and getting professional capacity."""
        metrics_engine.set_professional_capacity("user-1", 30.0)
        capacity = metrics_engine._get_professional_capacity("user-1")
        assert capacity == 30.0

    def test_generate_cache_key_unique(self, metrics_engine):
        """Test that cache keys are unique for different parameters."""
        key1 = metrics_engine._generate_cache_key("prefix", "user-1", [1, 2])
        key2 = metrics_engine._generate_cache_key("prefix", "user-1", [1, 3])
        key3 = metrics_engine._generate_cache_key("prefix", "user-2", [1, 2])
        
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_generate_cache_key_same_params(self, metrics_engine):
        """Test that same parameters generate same cache key."""
        key1 = metrics_engine._generate_cache_key("prefix", "user-1", [1, 2])
        key2 = metrics_engine._generate_cache_key("prefix", "user-1", [1, 2])
        
        assert key1 == key2

    def test_generate_cache_key_sprint_order_independent(self, metrics_engine):
        """Test that sprint order doesn't affect cache key."""
        key1 = metrics_engine._generate_cache_key("prefix", "user-1", [1, 2, 3])
        key2 = metrics_engine._generate_cache_key("prefix", "user-1", [3, 1, 2])
        
        assert key1 == key2


# =============================================================================
# Property 2: Consistência de Agregação de Alocação
# **Validates: Requirements 2.2, 2.3**
# =============================================================================

class TestAggregationConsistencyProperty:
    """
    Property test: aggregation consistency (Property 2)
    
    For any ProfessionalAllocation:
    - total_story_points == sum(project.story_points for project in project_breakdown)
    - total_issues == sum(project.issue_count for project in project_breakdown)
    """

    @given(
        project_data=st.lists(
            st.tuples(
                st.text(alphabet=st.characters(whitelist_categories=('Lu',)), min_size=2, max_size=4),
                st.lists(
                    st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
                    min_size=0,
                    max_size=10
                )
            ),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_aggregation_consistency(self, project_data, mock_connector, mock_cache):
        """
        **Validates: Requirements 2.2, 2.3**
        
        For any ProfessionalAllocation calculated:
        - total_story_points == sum(project.story_points for project in project_breakdown)
        - total_issues == sum(project.issue_count for project in project_breakdown)
        """
        # Ensure unique project keys
        seen_keys = set()
        unique_project_data = []
        for key, points in project_data:
            if key and key not in seen_keys:
                seen_keys.add(key)
                unique_project_data.append((key, points))
        
        assume(len(unique_project_data) > 0)
        
        engine = ProfessionalMetricsEngine(mock_connector, mock_cache)
        professional_id = "test-user"
        
        # Create issues from project data
        all_issues = []
        issue_counter = 0
        for project_key, story_points_list in unique_project_data:
            for sp in story_points_list:
                issue_counter += 1
                all_issues.append(create_issue(
                    jira_id=str(issue_counter),
                    project_key=project_key,
                    assignee_id=professional_id,
                    story_points=sp
                ))
        
        # Mock the connector to return our issues
        mock_result = MagicMock()
        mock_result.issues = all_issues
        mock_result.has_more = False
        mock_connector.get_issues.return_value = mock_result
        
        # Calculate allocation
        allocation = engine.calculate_cross_project_allocation(professional_id)
        
        # Verify Property 2: Aggregation consistency
        breakdown_sp_sum = sum(p.story_points for p in allocation.project_breakdown)
        breakdown_issue_sum = sum(p.issue_count for p in allocation.project_breakdown)
        
        assert abs(allocation.total_story_points - breakdown_sp_sum) < 0.0001, \
            f"total_story_points {allocation.total_story_points} != sum of breakdown {breakdown_sp_sum}"
        
        assert allocation.total_issues == breakdown_issue_sum, \
            f"total_issues {allocation.total_issues} != sum of breakdown {breakdown_issue_sum}"


# =============================================================================
# Property 3: Cálculo Correto da Taxa de Alocação
# **Validates: Requirement 2.4**
# =============================================================================

class TestAllocationRateCalculationProperty:
    """
    Property test: allocation rate calculation (Property 3)
    
    For any ProfessionalAllocation with capacity > 0:
    allocation_rate = (total_story_points / capacity) * 100
    """

    @given(
        story_points_list=st.lists(
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
            min_size=0,
            max_size=20
        ),
        capacity=st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_allocation_rate_formula(self, story_points_list, capacity, mock_connector, mock_cache):
        """
        **Validates: Requirement 2.4**
        
        For any ProfessionalAllocation with capacity > 0:
        allocation_rate = (total_story_points / capacity) * 100
        """
        engine = ProfessionalMetricsEngine(mock_connector, mock_cache, default_capacity=capacity)
        professional_id = "test-user"
        
        # Create issues with the given story points
        issues = [
            create_issue(
                jira_id=str(i),
                project_key="PROJ",
                assignee_id=professional_id,
                story_points=sp
            )
            for i, sp in enumerate(story_points_list)
        ]
        
        # Mock the connector
        mock_result = MagicMock()
        mock_result.issues = issues
        mock_result.has_more = False
        mock_connector.get_issues.return_value = mock_result
        
        # Calculate allocation
        allocation = engine.calculate_cross_project_allocation(professional_id)
        
        # Expected calculation
        total_points = sum(story_points_list)
        expected_rate = (total_points / capacity) * 100
        
        # Verify Property 3: Allocation rate formula
        assert abs(allocation.total_allocation_rate - expected_rate) < 0.0001, \
            f"Allocation rate {allocation.total_allocation_rate} != expected {expected_rate}"


# =============================================================================
# Property 6: Ordenação do Breakdown por Story Points
# **Validates: Requirement 3.4**
# =============================================================================

class TestBreakdownSortingProperty:
    """
    Property test: breakdown sorting (Property 6)
    
    For any ProfessionalAllocation, project_breakdown must be sorted
    by story_points in descending order.
    """

    @given(
        project_points=st.lists(
            st.tuples(
                st.text(alphabet=st.characters(whitelist_categories=('Lu',)), min_size=2, max_size=4),
                st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
            ),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_breakdown_sorted_descending(self, project_points, mock_connector, mock_cache):
        """
        **Validates: Requirement 3.4**
        
        For any ProfessionalAllocation, project_breakdown must be sorted
        by story_points in descending order.
        """
        # Ensure unique project keys
        seen_keys = set()
        unique_project_points = []
        for key, points in project_points:
            if key and key not in seen_keys:
                seen_keys.add(key)
                unique_project_points.append((key, points))
        
        assume(len(unique_project_points) >= 2)
        
        engine = ProfessionalMetricsEngine(mock_connector, mock_cache)
        professional_id = "test-user"
        
        # Create one issue per project with the specified story points
        issues = [
            create_issue(
                jira_id=str(i),
                project_key=key,
                assignee_id=professional_id,
                story_points=points
            )
            for i, (key, points) in enumerate(unique_project_points)
        ]
        
        # Mock the connector
        mock_result = MagicMock()
        mock_result.issues = issues
        mock_result.has_more = False
        mock_connector.get_issues.return_value = mock_result
        
        # Calculate allocation
        allocation = engine.calculate_cross_project_allocation(professional_id)
        
        # Verify Property 6: Breakdown is sorted by story_points descending
        breakdown_points = [p.story_points for p in allocation.project_breakdown]
        
        for i in range(len(breakdown_points) - 1):
            assert breakdown_points[i] >= breakdown_points[i + 1], \
                f"Breakdown not sorted: {breakdown_points[i]} < {breakdown_points[i + 1]} at index {i}"


# =============================================================================
# Property 7: Classificação Correta de Status de Alocação
# **Validates: Requirement 4.1**
# =============================================================================

class TestStatusClassificationProperty:
    """
    Property test: status classification (Property 7)
    
    For any allocation rate and thresholds:
    - allocation_rate > upper_threshold → OVERLOADED
    - allocation_rate < lower_threshold → UNDERUTILIZED
    - otherwise → NORMAL
    """

    @given(
        allocation_rate=st.floats(min_value=0.0, max_value=300.0, allow_nan=False, allow_infinity=False),
        upper_threshold=st.floats(min_value=50.0, max_value=150.0, allow_nan=False, allow_infinity=False),
        lower_threshold=st.floats(min_value=10.0, max_value=80.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_status_classification_thresholds(
        self, allocation_rate, upper_threshold, lower_threshold, mock_connector, mock_cache
    ):
        """
        **Validates: Requirement 4.1**
        
        For any allocation rate and thresholds:
        - allocation_rate > upper_threshold → OVERLOADED
        - allocation_rate < lower_threshold → UNDERUTILIZED
        - otherwise → NORMAL
        """
        # Ensure lower_threshold < upper_threshold
        assume(lower_threshold < upper_threshold)
        
        engine = ProfessionalMetricsEngine(
            mock_connector, 
            mock_cache,
            upper_threshold=upper_threshold,
            lower_threshold=lower_threshold
        )
        
        status = engine._classify_status(allocation_rate)
        
        # Verify Property 7: Status classification
        if allocation_rate > upper_threshold:
            assert status == AllocationStatus.OVERLOADED, \
                f"Rate {allocation_rate} > {upper_threshold} should be OVERLOADED, got {status}"
        elif allocation_rate < lower_threshold:
            assert status == AllocationStatus.UNDERUTILIZED, \
                f"Rate {allocation_rate} < {lower_threshold} should be UNDERUTILIZED, got {status}"
        else:
            assert status == AllocationStatus.NORMAL, \
                f"Rate {allocation_rate} in [{lower_threshold}, {upper_threshold}] should be NORMAL, got {status}"


# =============================================================================
# Property 10: Validação de Modelos de Dados
# **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**
# =============================================================================

class TestModelValidationProperty:
    """
    Property test: model validation (Property 10)
    
    For any instance of model:
    - Professional: account_id and display_name cannot be empty
    - ProfessionalAllocation: total_allocation_rate >= 0 and capacity > 0
    - ProjectAllocation: 0 <= allocation_percentage <= 100, story_points >= 0, issue_count >= 0
    """

    @given(
        account_id=st.text(min_size=0, max_size=20),
        display_name=st.text(min_size=0, max_size=50)
    )
    @settings(max_examples=100)
    def test_professional_validation(self, account_id, display_name):
        """
        **Validates: Requirements 8.1, 8.2**
        
        Professional: account_id and display_name cannot be empty
        """
        account_id_valid = bool(account_id and account_id.strip())
        display_name_valid = bool(display_name and display_name.strip())
        
        if account_id_valid and display_name_valid:
            # Should succeed
            prof = Professional(account_id=account_id, display_name=display_name)
            assert prof.account_id == account_id
            assert prof.display_name == display_name
        else:
            # Should raise ValueError
            with pytest.raises(ValueError):
                Professional(account_id=account_id, display_name=display_name)

    @given(
        total_allocation_rate=st.floats(min_value=-100.0, max_value=500.0, allow_nan=False, allow_infinity=False),
        capacity=st.floats(min_value=-50.0, max_value=200.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_professional_allocation_validation(self, total_allocation_rate, capacity):
        """
        **Validates: Requirements 8.3, 8.4**
        
        ProfessionalAllocation: total_allocation_rate >= 0 and capacity > 0
        """
        rate_valid = total_allocation_rate >= 0
        capacity_valid = capacity > 0
        
        if rate_valid and capacity_valid:
            # Should succeed
            alloc = ProfessionalAllocation(
                professional_id="test-user",
                professional_name="Test User",
                total_allocation_rate=total_allocation_rate,
                total_story_points=10.0,
                total_issues=5,
                project_breakdown=[],
                status=AllocationStatus.NORMAL,
                capacity=capacity
            )
            assert alloc.total_allocation_rate == total_allocation_rate
            assert alloc.capacity == capacity
        else:
            # Should raise ValueError
            with pytest.raises(ValueError):
                ProfessionalAllocation(
                    professional_id="test-user",
                    professional_name="Test User",
                    total_allocation_rate=total_allocation_rate,
                    total_story_points=10.0,
                    total_issues=5,
                    project_breakdown=[],
                    status=AllocationStatus.NORMAL,
                    capacity=capacity
                )

    @given(
        allocation_percentage=st.floats(min_value=-50.0, max_value=150.0, allow_nan=False, allow_infinity=False),
        story_points=st.floats(min_value=-50.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        issue_count=st.integers(min_value=-10, max_value=100)
    )
    @settings(max_examples=100)
    def test_project_allocation_validation(self, allocation_percentage, story_points, issue_count):
        """
        **Validates: Requirements 8.5, 8.6**
        
        ProjectAllocation: 0 <= allocation_percentage <= 100, story_points >= 0, issue_count >= 0
        """
        percentage_valid = 0 <= allocation_percentage <= 100
        sp_valid = story_points >= 0
        count_valid = issue_count >= 0
        
        if percentage_valid and sp_valid and count_valid:
            # Should succeed
            proj_alloc = ProjectAllocation(
                project_key="PROJ",
                project_name="Test Project",
                story_points=story_points,
                issue_count=issue_count,
                allocation_percentage=allocation_percentage
            )
            assert proj_alloc.allocation_percentage == allocation_percentage
            assert proj_alloc.story_points == story_points
            assert proj_alloc.issue_count == issue_count
        else:
            # Should raise ValueError
            with pytest.raises(ValueError):
                ProjectAllocation(
                    project_key="PROJ",
                    project_name="Test Project",
                    story_points=story_points,
                    issue_count=issue_count,
                    allocation_percentage=allocation_percentage
                )


# =============================================================================
# Additional Unit Tests for Edge Cases
# =============================================================================

class TestEdgeCases:
    """Additional unit tests for edge cases."""

    def test_empty_issues_returns_zero_allocation(self, mock_connector, mock_cache):
        """Test that empty issues result in zero allocation."""
        engine = ProfessionalMetricsEngine(mock_connector, mock_cache)
        
        mock_result = MagicMock()
        mock_result.issues = []
        mock_result.has_more = False
        mock_connector.get_issues.return_value = mock_result
        
        allocation = engine.calculate_cross_project_allocation("test-user")
        
        assert allocation.total_story_points == 0.0
        assert allocation.total_issues == 0
        assert allocation.total_allocation_rate == 0.0
        assert len(allocation.project_breakdown) == 0

    def test_issues_without_story_points_counted(self, mock_connector, mock_cache):
        """Test that issues without story points are still counted."""
        engine = ProfessionalMetricsEngine(mock_connector, mock_cache)
        
        issues = [
            create_issue("1", "PROJ", "test-user", story_points=None),
            create_issue("2", "PROJ", "test-user", story_points=5.0),
        ]
        
        mock_result = MagicMock()
        mock_result.issues = issues
        mock_result.has_more = False
        mock_connector.get_issues.return_value = mock_result
        
        allocation = engine.calculate_cross_project_allocation("test-user")
        
        assert allocation.total_issues == 2
        assert allocation.total_story_points == 5.0

    def test_allocation_percentage_sums_to_100(self, mock_connector, mock_cache):
        """Test that allocation percentages sum to 100% when there are story points."""
        engine = ProfessionalMetricsEngine(mock_connector, mock_cache)
        
        issues = [
            create_issue("1", "PROJ1", "test-user", story_points=10.0),
            create_issue("2", "PROJ2", "test-user", story_points=20.0),
            create_issue("3", "PROJ3", "test-user", story_points=30.0),
        ]
        
        mock_result = MagicMock()
        mock_result.issues = issues
        mock_result.has_more = False
        mock_connector.get_issues.return_value = mock_result
        
        allocation = engine.calculate_cross_project_allocation("test-user")
        
        total_percentage = sum(p.allocation_percentage for p in allocation.project_breakdown)
        assert abs(total_percentage - 100.0) < 0.01

    def test_custom_thresholds_applied(self, mock_connector, mock_cache):
        """Test that custom thresholds are applied correctly."""
        engine = ProfessionalMetricsEngine(
            mock_connector, 
            mock_cache,
            upper_threshold=80.0,
            lower_threshold=30.0
        )
        
        # 75% should be normal with default thresholds but overloaded with custom
        assert engine._classify_status(85.0) == AllocationStatus.OVERLOADED
        assert engine._classify_status(25.0) == AllocationStatus.UNDERUTILIZED
        assert engine._classify_status(50.0) == AllocationStatus.NORMAL
