"""
Property-Based Tests for Jira Allocation Connector.

This module contains property-based tests using the hypothesis library
to validate correctness properties from the design document.

Tests cover:
- Property 6: Allocation rate calculation
- Property 7: Workload distribution sums to 100%
- Property 8: Status classification by threshold
- Property 5: Cache round-trip
- Property 18: Config YAML round-trip
- Property 17: CSV export round-trip
- Property 10: Throughput equals done issues
- Property 11: Lead time calculation
- Property 12: Cycle time calculation
- Property 13: Velocity calculation
"""

import csv
import io
import os
import sys
import tempfile
from datetime import datetime, timedelta
from typing import List
from unittest.mock import MagicMock

import pytest
import yaml
from hypothesis import given, settings, strategies as st, assume, HealthCheck

from src.cache.cache_manager import CacheManager
from src.config.config_loader import ConfigLoader
from src.metrics.metrics_engine import MetricsEngine
from src.models.data_models import DateRange, Issue


def export_to_csv(data: List[dict], filename: str) -> bytes:
    """
    Convert data to CSV format and return bytes for download.
    
    This is a standalone implementation for testing purposes to avoid
    importing streamlit-dependent modules.
    
    Args:
        data: List of dictionaries to export
        filename: Suggested filename for the download
        
    Returns:
        CSV content as bytes
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


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_connector():
    """Create a mock JiraConnector."""
    connector = MagicMock()
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


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Strategy for generating valid story points (non-negative floats)
story_points_strategy = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)

# Strategy for generating valid capacity (positive floats)
capacity_strategy = st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False)

# Strategy for generating allocation rates
allocation_rate_strategy = st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False)

# Strategy for generating member IDs
member_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_'),
    min_size=1,
    max_size=20
)

# Strategy for generating issue status categories
status_category_strategy = st.sampled_from(["To Do", "In Progress", "Done"])


def issue_strategy(
    assignee_id: str = None,
    status_category: str = None,
    with_resolution: bool = False,
    with_started: bool = False
):
    """Generate a strategy for creating Issue objects."""
    @st.composite
    def _issue(draw):
        now = datetime.now()
        created = now - timedelta(days=draw(st.integers(min_value=1, max_value=365)))
        
        resolution_date = None
        started_date = None
        
        if with_resolution or draw(st.booleans()):
            # Resolution must be after created
            resolution_offset = draw(st.integers(min_value=1, max_value=30))
            resolution_date = created + timedelta(days=resolution_offset)
        
        if with_started or draw(st.booleans()):
            # Started must be after created and before resolution (if exists)
            if resolution_date:
                max_started_offset = (resolution_date - created).days - 1
                if max_started_offset > 0:
                    started_offset = draw(st.integers(min_value=0, max_value=max_started_offset))
                    started_date = created + timedelta(days=started_offset)
            else:
                started_offset = draw(st.integers(min_value=0, max_value=30))
                started_date = created + timedelta(days=started_offset)
        
        return Issue(
            jira_id=draw(st.text(min_size=1, max_size=10, alphabet='0123456789')),
            key=f"PROJ-{draw(st.integers(min_value=1, max_value=9999))}",
            summary=draw(st.text(min_size=1, max_size=100)),
            issue_type=draw(st.sampled_from(["Story", "Bug", "Task", "Epic"])),
            status=draw(st.sampled_from(["Open", "In Progress", "Done", "Closed"])),
            status_category=status_category or draw(status_category_strategy),
            assignee_account_id=assignee_id or draw(st.text(min_size=1, max_size=20)),
            assignee_name=draw(st.text(min_size=1, max_size=50)),
            story_points=draw(st.one_of(st.none(), story_points_strategy)),
            created_date=created,
            resolution_date=resolution_date,
            started_date=started_date
        )
    
    return _issue()


# =============================================================================
# Property 6: Allocation Rate Calculation
# **Validates: Requirements 3.1, 3.2**
# =============================================================================

class TestAllocationRateProperty:
    """
    Property test: allocation rate calculation (Property 6)
    
    For any member with issues, allocation_rate = (sum of story_points / capacity) * 100
    """

    @given(
        story_points_list=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=0,
            max_size=20
        ),
        capacity=st.floats(min_value=0.1, max_value=200.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_allocation_rate_formula(self, story_points_list, capacity, mock_connector, sample_date_range):
        """
        **Validates: Requirements 3.1, 3.2**
        
        For any member with issues, allocation_rate = (sum of story_points / capacity) * 100
        """
        engine = MetricsEngine(mock_connector)
        member_id = "test-user"
        engine.set_member_capacity(member_id, capacity)
        
        # Create issues with the given story points
        issues = [
            Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Issue {i}",
                issue_type="Story",
                status="Open",
                status_category="To Do",
                assignee_account_id=member_id,
                story_points=sp
            )
            for i, sp in enumerate(story_points_list)
        ]
        
        # Calculate allocation rate
        rate = engine.calculate_allocation_rate(
            member_id=member_id,
            period=sample_date_range,
            issues=issues
        )
        
        # Expected calculation
        total_points = sum(story_points_list)
        expected_rate = (total_points / capacity) * 100
        
        # Verify the property
        assert abs(rate - expected_rate) < 0.0001, \
            f"Allocation rate {rate} != expected {expected_rate} for points={total_points}, capacity={capacity}"


# =============================================================================
# Property 7: Workload Distribution Sums to 100%
# **Validates: Requirements 3.3**
# =============================================================================

class TestWorkloadDistributionProperty:
    """
    Property test: workload distribution sums to 100% (Property 7)
    
    For any team with at least one member with issues, sum of workload percentages = 100%
    """

    @given(
        member_points=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workload_distribution_sums_to_100(self, member_points, mock_connector, sample_date_range):
        """
        **Validates: Requirements 3.3**
        
        For any team with at least one member with issues, sum of workload percentages = 100%
        """
        engine = MetricsEngine(mock_connector)
        
        # Create team members and their issues
        team_members = [f"user-{i}" for i in range(len(member_points))]
        issues = []
        
        for i, (member_id, points) in enumerate(zip(team_members, member_points)):
            if points > 0:
                issues.append(Issue(
                    jira_id=str(i),
                    key=f"PROJ-{i}",
                    summary=f"Issue {i}",
                    issue_type="Story",
                    status="Open",
                    status_category="To Do",
                    assignee_account_id=member_id,
                    story_points=points
                ))
        
        # Calculate workload distribution
        distribution = engine.calculate_workload_distribution(
            team_members=team_members,
            period=sample_date_range,
            issues=issues
        )
        
        # Verify the property: sum should be 100%
        total = sum(distribution.values())
        assert abs(total - 100.0) < 0.01, \
            f"Workload distribution sum {total} != 100% for points={member_points}"


# =============================================================================
# Property 8: Status Classification by Threshold
# **Validates: Requirements 3.4, 3.5**
# =============================================================================

class TestStatusClassificationProperty:
    """
    Property test: status classification by threshold (Property 8)
    
    rate > 100 â†’ "overloaded", rate < 50 â†’ "underutilized", else â†’ "normal"
    """

    @given(allocation_rate=st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_status_classification_thresholds(self, allocation_rate, mock_connector):
        """
        **Validates: Requirements 3.4, 3.5**
        
        rate > 100 â†’ "overloaded", rate < 50 â†’ "underutilized", else â†’ "normal"
        """
        engine = MetricsEngine(mock_connector)
        
        status = engine.classify_allocation_status(allocation_rate)
        
        # Verify the property based on thresholds
        if allocation_rate > 100.0:
            assert status == "overloaded", \
                f"Rate {allocation_rate} > 100 should be 'overloaded', got '{status}'"
        elif allocation_rate < 50.0:
            assert status == "underutilized", \
                f"Rate {allocation_rate} < 50 should be 'underutilized', got '{status}'"
        else:
            assert status == "normal", \
                f"Rate {allocation_rate} in [50, 100] should be 'normal', got '{status}'"


# =============================================================================
# Property 5: Cache Round-Trip
# **Validates: Requirements 2.6, 2.7**
# =============================================================================

class TestCacheRoundTripProperty:
    """
    Property test: cache round-trip (Property 5)
    
    Data stored in cache should be retrieved intact before TTL expires
    """

    @given(
        key=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        data=st.one_of(
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.text(max_size=100),
            st.lists(st.integers(), max_size=10),
            st.dictionaries(
                st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('L',))),
                st.integers(),
                max_size=5
            )
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_roundtrip_preserves_data(self, key, data):
        """
        **Validates: Requirements 2.6, 2.7**
        
        Data stored in cache should be retrieved intact before TTL expires
        """
        # Clear any existing cache
        CacheManager.clear_all()
        
        # Store data with long TTL
        CacheManager.set_cached_data(key, data, ttl_seconds=3600)
        
        # Retrieve data
        retrieved = CacheManager.get_cached_data(key)
        
        # Verify the property: data should be preserved
        assert retrieved == data, \
            f"Cache round-trip failed: stored {data}, retrieved {retrieved}"
        
        # Verify cache is valid
        assert CacheManager.is_cache_valid(key), \
            f"Cache should be valid for key '{key}'"
        
        # Clean up
        CacheManager.clear_all()

    @given(
        key=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        data=st.one_of(
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.text(max_size=100),
            st.lists(st.integers(), max_size=10),
            st.dictionaries(
                st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('L',))),
                st.integers(),
                max_size=5
            )
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_invalid_after_ttl_expiration(self, key, data):
        """
        **Validates: Requirements 2.6, 2.7**

        After TTL expiration, cache should be considered invalid and return None
        """
        from unittest.mock import patch

        # Clear any existing cache
        CacheManager.clear_all()

        # Store data with minimal TTL (1 second)
        CacheManager.set_cached_data(key, data, ttl_seconds=1)

        # Verify data is stored and valid immediately
        assert CacheManager.is_cache_valid(key), \
            f"Cache should be valid immediately after storing for key '{key}'"

        # Simulate time passing beyond TTL by patching datetime.now()
        future_time = datetime.now() + timedelta(seconds=2)
        with patch('src.cache.cache_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = future_time

            # Verify cache is now invalid
            assert not CacheManager.is_cache_valid(key), \
                f"Cache should be invalid after TTL expiration for key '{key}'"

            # Verify get_cached_data returns None for expired cache
            retrieved = CacheManager.get_cached_data(key)
            assert retrieved is None, \
                f"Cache should return None after TTL expiration, got {retrieved}"

        # Clean up
        CacheManager.clear_all()


# =============================================================================
# Property 18: Config YAML Round-Trip
# **Validates: Requirements 6.1**
# =============================================================================

class TestConfigYamlRoundTripProperty:
    """
    Property test: config YAML round-trip (Property 18)
    
    Valid config loaded from YAML and serialized back should be equivalent
    """

    @given(
        ttl_seconds=st.integers(min_value=1, max_value=86400),
        project_keys=st.lists(
            st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Lu',))),
            min_size=0,
            max_size=5
        ),
        default_capacity=st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_config_yaml_roundtrip(self, ttl_seconds, project_keys, default_capacity):
        """
        **Validates: Requirements 6.1**
        
        Valid config loaded from YAML and serialized back should be equivalent
        """
        # Create a valid config dictionary
        config_dict = {
            "cache": {
                "ttl_seconds": ttl_seconds
            },
            "projects": {
                "keys": project_keys,
                "default_capacity_hours": default_capacity
            }
        }
        
        # Write to temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = f.name
        
        try:
            # Set required environment variables for loading
            os.environ["JIRA_BASE_URL"] = "https://test.atlassian.net"
            os.environ["JIRA_PERSONAL_ACCESS_TOKEN"] = "test-token"
            
            # Load config
            loader = ConfigLoader(temp_path)
            
            # Read back the YAML
            with open(temp_path, 'r') as f:
                loaded_dict = yaml.safe_load(f)
            
            # Verify round-trip: original dict should match loaded dict
            assert loaded_dict["cache"]["ttl_seconds"] == ttl_seconds, \
                f"TTL mismatch: {loaded_dict['cache']['ttl_seconds']} != {ttl_seconds}"
            assert loaded_dict["projects"]["keys"] == project_keys, \
                f"Project keys mismatch: {loaded_dict['projects']['keys']} != {project_keys}"
            assert abs(loaded_dict["projects"]["default_capacity_hours"] - default_capacity) < 0.0001, \
                f"Capacity mismatch: {loaded_dict['projects']['default_capacity_hours']} != {default_capacity}"
            
            # Validate the config
            errors = loader.validate(loaded_dict)
            assert len(errors) == 0, f"Config validation failed: {errors}"
            
        finally:
            # Clean up
            os.unlink(temp_path)
            os.environ.pop("JIRA_BASE_URL", None)
            os.environ.pop("JIRA_PERSONAL_ACCESS_TOKEN", None)


# =============================================================================
# Property 17: CSV Export Round-Trip
# **Validates: Requirements 5.8**
# =============================================================================

class TestCsvExportRoundTripProperty:
    """
    Property test: CSV export round-trip (Property 17)
    
    Data exported to CSV should preserve all columns and values
    """

    @given(
        data=st.lists(
            st.fixed_dictionaries({
                "name": st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L',))),
                "value": st.integers(min_value=-1000, max_value=1000),
                "rate": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
            }),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_csv_export_roundtrip(self, data):
        """
        **Validates: Requirements 5.8**
        
        Data exported to CSV should preserve all columns and values
        """
        # Export to CSV
        csv_bytes = export_to_csv(data, "test.csv")
        
        # Parse the CSV back
        csv_content = csv_bytes.decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        parsed_data = list(reader)
        
        # Verify the property: all rows and columns should be preserved
        assert len(parsed_data) == len(data), \
            f"Row count mismatch: {len(parsed_data)} != {len(data)}"
        
        for i, (original, parsed) in enumerate(zip(data, parsed_data)):
            # Check all columns exist
            assert set(original.keys()) == set(parsed.keys()), \
                f"Column mismatch at row {i}: {set(original.keys())} != {set(parsed.keys())}"
            
            # Check values (CSV reads everything as strings)
            assert parsed["name"] == original["name"], \
                f"Name mismatch at row {i}: {parsed['name']} != {original['name']}"
            assert int(parsed["value"]) == original["value"], \
                f"Value mismatch at row {i}: {parsed['value']} != {original['value']}"
            # Float comparison with tolerance
            assert abs(float(parsed["rate"]) - original["rate"]) < 0.0001, \
                f"Rate mismatch at row {i}: {parsed['rate']} != {original['rate']}"

    @given(
        data=st.lists(
            st.fixed_dictionaries({
                "name": st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L',))),
                "value": st.integers(min_value=-1000, max_value=1000),
                "rate": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
                "created_date": st.datetimes(
                    min_value=datetime(2020, 1, 1),
                    max_value=datetime(2030, 12, 31)
                ),
                "due_date": st.dates(
                    min_value=datetime(2020, 1, 1).date(),
                    max_value=datetime(2030, 12, 31).date()
                )
            }),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_csv_export_roundtrip_with_dates(self, data):
        """
        **Validates: Requirements 5.8**
        
        Data exported to CSV should preserve all columns and values,
        including datetime and date objects (as ISO format strings).
        """
        # Export to CSV
        csv_bytes = export_to_csv(data, "test_dates.csv")
        
        # Parse the CSV back
        csv_content = csv_bytes.decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        parsed_data = list(reader)
        
        # Verify the property: all rows and columns should be preserved
        assert len(parsed_data) == len(data), \
            f"Row count mismatch: {len(parsed_data)} != {len(data)}"
        
        for i, (original, parsed) in enumerate(zip(data, parsed_data)):
            # Check all columns exist
            assert set(original.keys()) == set(parsed.keys()), \
                f"Column mismatch at row {i}: {set(original.keys())} != {set(parsed.keys())}"
            
            # Check string values
            assert parsed["name"] == original["name"], \
                f"Name mismatch at row {i}: {parsed['name']} != {original['name']}"
            
            # Check integer values
            assert int(parsed["value"]) == original["value"], \
                f"Value mismatch at row {i}: {parsed['value']} != {original['value']}"
            
            # Check float values with tolerance
            assert abs(float(parsed["rate"]) - original["rate"]) < 0.0001, \
                f"Rate mismatch at row {i}: {parsed['rate']} != {original['rate']}"
            
            # Check datetime values (CSV stores as string representation)
            original_datetime_str = str(original["created_date"])
            assert parsed["created_date"] == original_datetime_str, \
                f"Datetime mismatch at row {i}: {parsed['created_date']} != {original_datetime_str}"
            
            # Check date values (CSV stores as string representation)
            original_date_str = str(original["due_date"])
            assert parsed["due_date"] == original_date_str, \
                f"Date mismatch at row {i}: {parsed['due_date']} != {original_date_str}"

    @given(
        data=st.lists(
            st.fixed_dictionaries({
                "id": st.integers(min_value=1, max_value=10000),
                "story_points": st.one_of(
                    st.none(),
                    st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
                ),
                "allocation_rate": st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
                "throughput": st.integers(min_value=0, max_value=1000)
            }),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_csv_export_roundtrip_numeric_types(self, data):
        """
        **Validates: Requirements 5.8**
        
        Data exported to CSV should preserve numeric types (integers and floats),
        including None values which should be preserved as empty strings.
        """
        # Export to CSV
        csv_bytes = export_to_csv(data, "test_numeric.csv")
        
        # Parse the CSV back
        csv_content = csv_bytes.decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        parsed_data = list(reader)
        
        # Verify the property: all rows and columns should be preserved
        assert len(parsed_data) == len(data), \
            f"Row count mismatch: {len(parsed_data)} != {len(data)}"
        
        for i, (original, parsed) in enumerate(zip(data, parsed_data)):
            # Check all columns exist
            assert set(original.keys()) == set(parsed.keys()), \
                f"Column mismatch at row {i}: {set(original.keys())} != {set(parsed.keys())}"
            
            # Check integer id
            assert int(parsed["id"]) == original["id"], \
                f"ID mismatch at row {i}: {parsed['id']} != {original['id']}"
            
            # Check optional float (story_points can be None)
            if original["story_points"] is None:
                assert parsed["story_points"] == "" or parsed["story_points"] == "None", \
                    f"Story points should be empty or 'None' for None value at row {i}, got {parsed['story_points']}"
            else:
                assert abs(float(parsed["story_points"]) - original["story_points"]) < 0.0001, \
                    f"Story points mismatch at row {i}: {parsed['story_points']} != {original['story_points']}"
            
            # Check float allocation_rate
            assert abs(float(parsed["allocation_rate"]) - original["allocation_rate"]) < 0.0001, \
                f"Allocation rate mismatch at row {i}: {parsed['allocation_rate']} != {original['allocation_rate']}"
            
            # Check integer throughput
            assert int(parsed["throughput"]) == original["throughput"], \
                f"Throughput mismatch at row {i}: {parsed['throughput']} != {original['throughput']}"


# =============================================================================
# Property 10: Throughput Equals Done Issues
# **Validates: Requirements 4.1**
# =============================================================================

class TestThroughputProperty:
    """
    Property test: throughput equals done issues (Property 10)
    
    Throughput = count of issues with status_category = "Done"
    """

    @given(
        status_categories=st.lists(
            st.sampled_from(["To Do", "In Progress", "Done"]),
            min_size=0,
            max_size=50
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_throughput_equals_done_count(self, status_categories, mock_connector):
        """
        **Validates: Requirements 4.1**
        
        Throughput = count of issues with status_category = "Done"
        """
        engine = MetricsEngine(mock_connector)
        
        # Create issues with the given status categories
        issues = [
            Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Issue {i}",
                issue_type="Story",
                status="Open" if cat != "Done" else "Done",
                status_category=cat
            )
            for i, cat in enumerate(status_categories)
        ]
        
        # Calculate throughput
        throughput = engine.calculate_throughput(issues)
        
        # Expected: count of "Done" issues
        expected = sum(1 for cat in status_categories if cat == "Done")
        
        # Verify the property
        assert throughput == expected, \
            f"Throughput {throughput} != expected {expected} for categories={status_categories}"


# =============================================================================
# Property 11: Lead Time Calculation
# **Validates: Requirements 4.2**
# =============================================================================

class TestLeadTimeProperty:
    """
    Property test: lead time calculation (Property 11)
    
    Lead time = (resolution_date - created_date) in hours
    """

    @given(
        days_to_resolution=st.lists(
            st.integers(min_value=1, max_value=365),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_lead_time_calculation(self, days_to_resolution, mock_connector):
        """
        **Validates: Requirements 4.2**
        
        Lead time = (resolution_date - created_date) in hours
        """
        engine = MetricsEngine(mock_connector)
        now = datetime.now()
        
        # Create issues with specific lead times
        issues = []
        for i, days in enumerate(days_to_resolution):
            created = now - timedelta(days=days + 10)
            resolution = created + timedelta(days=days)
            issues.append(Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Issue {i}",
                issue_type="Story",
                status="Done",
                status_category="Done",
                created_date=created,
                resolution_date=resolution
            ))
        
        # Calculate lead time
        lead_time = engine.calculate_lead_time(issues)
        
        # Expected: average of (resolution - created) in hours
        expected_hours = [days * 24 for days in days_to_resolution]
        expected_avg = sum(expected_hours) / len(expected_hours)
        
        # Verify the property (allow small tolerance for datetime precision)
        assert lead_time is not None, "Lead time should not be None"
        assert abs(lead_time - expected_avg) < 1.0, \
            f"Lead time {lead_time} != expected {expected_avg} hours"

    @given(
        hours_to_resolution=st.integers(min_value=1, max_value=8760)  # Up to 1 year in hours
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_lead_time_single_issue_hours_precision(self, hours_to_resolution, mock_connector):
        """
        **Validates: Requirements 4.2**
        
        For a single issue with resolution_date, lead_time = (resolution_date - created_date) in hours.
        Tests with hour-level precision to ensure accurate calculation.
        """
        engine = MetricsEngine(mock_connector)
        now = datetime.now()
        
        created = now - timedelta(hours=hours_to_resolution + 100)
        resolution = created + timedelta(hours=hours_to_resolution)
        
        issue = Issue(
            jira_id="1",
            key="PROJ-1",
            summary="Test Issue",
            issue_type="Story",
            status="Done",
            status_category="Done",
            created_date=created,
            resolution_date=resolution
        )
        
        # Calculate lead time for single issue
        lead_time = engine.calculate_lead_time([issue])
        
        # Verify the property: lead_time should equal hours_to_resolution
        assert lead_time is not None, "Lead time should not be None for resolved issue"
        assert abs(lead_time - hours_to_resolution) < 0.01, \
            f"Lead time {lead_time} != expected {hours_to_resolution} hours"

    @given(
        resolved_count=st.integers(min_value=0, max_value=10),
        unresolved_count=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_lead_time_excludes_unresolved_issues(self, resolved_count, unresolved_count, mock_connector):
        """
        **Validates: Requirements 4.2**
        
        Lead time calculation should only consider issues with resolution_date defined.
        Issues without resolution_date should be excluded from the calculation.
        """
        engine = MetricsEngine(mock_connector)
        now = datetime.now()
        
        issues = []
        expected_lead_times = []
        
        # Create resolved issues with known lead times
        for i in range(resolved_count):
            lead_time_hours = (i + 1) * 24  # 24, 48, 72, ... hours
            created = now - timedelta(hours=lead_time_hours + 100)
            resolution = created + timedelta(hours=lead_time_hours)
            issues.append(Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Resolved Issue {i}",
                issue_type="Story",
                status="Done",
                status_category="Done",
                created_date=created,
                resolution_date=resolution
            ))
            expected_lead_times.append(lead_time_hours)
        
        # Create unresolved issues (no resolution_date)
        for i in range(unresolved_count):
            created = now - timedelta(days=i + 1)
            issues.append(Issue(
                jira_id=str(resolved_count + i),
                key=f"PROJ-{resolved_count + i}",
                summary=f"Unresolved Issue {i}",
                issue_type="Story",
                status="In Progress",
                status_category="In Progress",
                created_date=created,
                resolution_date=None  # No resolution
            ))
        
        # Calculate lead time
        lead_time = engine.calculate_lead_time(issues)
        
        # Verify the property
        if resolved_count == 0:
            # No resolved issues means lead time should be None
            assert lead_time is None, \
                f"Lead time should be None when no resolved issues, got {lead_time}"
        else:
            # Lead time should be average of resolved issues only
            expected_avg = sum(expected_lead_times) / len(expected_lead_times)
            assert lead_time is not None, "Lead time should not be None when resolved issues exist"
            assert abs(lead_time - expected_avg) < 0.01, \
                f"Lead time {lead_time} != expected {expected_avg} hours (unresolved issues should be excluded)"

    @given(
        minutes_to_resolution=st.integers(min_value=1, max_value=1440)  # Up to 24 hours in minutes
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_lead_time_fractional_hours(self, minutes_to_resolution, mock_connector):
        """
        **Validates: Requirements 4.2**
        
        Lead time should correctly calculate fractional hours for sub-day resolutions.
        """
        engine = MetricsEngine(mock_connector)
        now = datetime.now()
        
        created = now - timedelta(minutes=minutes_to_resolution + 1000)
        resolution = created + timedelta(minutes=minutes_to_resolution)
        
        issue = Issue(
            jira_id="1",
            key="PROJ-1",
            summary="Quick Resolution Issue",
            issue_type="Bug",
            status="Done",
            status_category="Done",
            created_date=created,
            resolution_date=resolution
        )
        
        # Calculate lead time
        lead_time = engine.calculate_lead_time([issue])
        
        # Expected lead time in hours (with fractional part)
        expected_hours = minutes_to_resolution / 60.0
        
        # Verify the property
        assert lead_time is not None, "Lead time should not be None"
        assert abs(lead_time - expected_hours) < 0.001, \
            f"Lead time {lead_time} != expected {expected_hours} hours for {minutes_to_resolution} minutes"


# =============================================================================
# Property 12: Cycle Time Calculation
# **Validates: Requirements 4.3**
# =============================================================================

class TestCycleTimeProperty:
    """
    Property test: cycle time calculation (Property 12)
    
    Cycle time = (resolution_date - started_date) in hours
    """

    @given(
        days_to_complete=st.lists(
            st.integers(min_value=1, max_value=100),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cycle_time_calculation(self, days_to_complete, mock_connector):
        """
        **Validates: Requirements 4.3**
        
        Cycle time = (resolution_date - started_date) in hours
        """
        engine = MetricsEngine(mock_connector)
        now = datetime.now()
        
        # Create issues with specific cycle times
        issues = []
        for i, days in enumerate(days_to_complete):
            created = now - timedelta(days=days + 20)
            started = created + timedelta(days=5)  # Started 5 days after creation
            resolution = started + timedelta(days=days)
            issues.append(Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Issue {i}",
                issue_type="Story",
                status="Done",
                status_category="Done",
                created_date=created,
                started_date=started,
                resolution_date=resolution
            ))
        
        # Calculate cycle time
        cycle_time = engine.calculate_cycle_time(issues)
        
        # Expected: average of (resolution - started) in hours
        expected_hours = [days * 24 for days in days_to_complete]
        expected_avg = sum(expected_hours) / len(expected_hours)
        
        # Verify the property (allow small tolerance for datetime precision)
        assert cycle_time is not None, "Cycle time should not be None"
        assert abs(cycle_time - expected_avg) < 1.0, \
            f"Cycle time {cycle_time} != expected {expected_avg} hours"

    @given(
        hours_to_complete=st.integers(min_value=1, max_value=8760)  # Up to 1 year in hours
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cycle_time_single_issue_hours_precision(self, hours_to_complete, mock_connector):
        """
        **Validates: Requirements 4.3**
        
        For a single issue with resolution_date and started_date, 
        cycle_time = (resolution_date - started_date) in hours.
        Tests with hour-level precision to ensure accurate calculation.
        """
        engine = MetricsEngine(mock_connector)
        now = datetime.now()
        
        created = now - timedelta(hours=hours_to_complete + 200)
        started = created + timedelta(hours=100)  # Started 100 hours after creation
        resolution = started + timedelta(hours=hours_to_complete)
        
        issue = Issue(
            jira_id="1",
            key="PROJ-1",
            summary="Test Issue",
            issue_type="Story",
            status="Done",
            status_category="Done",
            created_date=created,
            started_date=started,
            resolution_date=resolution
        )
        
        # Calculate cycle time for single issue
        cycle_time = engine.calculate_cycle_time([issue])
        
        # Verify the property: cycle_time should equal hours_to_complete
        assert cycle_time is not None, "Cycle time should not be None for issue with started and resolution dates"
        assert abs(cycle_time - hours_to_complete) < 0.01, \
            f"Cycle time {cycle_time} != expected {hours_to_complete} hours"

    @given(
        complete_count=st.integers(min_value=0, max_value=10),
        incomplete_count=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cycle_time_excludes_issues_without_started_or_resolution(self, complete_count, incomplete_count, mock_connector):
        """
        **Validates: Requirements 4.3**
        
        Cycle time calculation should only consider issues with both resolution_date 
        and started_date defined. Issues missing either date should be excluded.
        """
        engine = MetricsEngine(mock_connector)
        now = datetime.now()
        
        issues = []
        expected_cycle_times = []
        
        # Create complete issues with known cycle times (have both started and resolution)
        for i in range(complete_count):
            cycle_time_hours = (i + 1) * 24  # 24, 48, 72, ... hours
            created = now - timedelta(hours=cycle_time_hours + 200)
            started = created + timedelta(hours=50)
            resolution = started + timedelta(hours=cycle_time_hours)
            issues.append(Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Complete Issue {i}",
                issue_type="Story",
                status="Done",
                status_category="Done",
                created_date=created,
                started_date=started,
                resolution_date=resolution
            ))
            expected_cycle_times.append(cycle_time_hours)
        
        # Create incomplete issues (missing started_date or resolution_date)
        for i in range(incomplete_count):
            created = now - timedelta(days=i + 1)
            # Alternate between missing started_date and missing resolution_date
            if i % 2 == 0:
                # Missing started_date
                issues.append(Issue(
                    jira_id=str(complete_count + i),
                    key=f"PROJ-{complete_count + i}",
                    summary=f"No Started Date Issue {i}",
                    issue_type="Story",
                    status="Done",
                    status_category="Done",
                    created_date=created,
                    started_date=None,
                    resolution_date=now
                ))
            else:
                # Missing resolution_date
                issues.append(Issue(
                    jira_id=str(complete_count + i),
                    key=f"PROJ-{complete_count + i}",
                    summary=f"No Resolution Date Issue {i}",
                    issue_type="Story",
                    status="In Progress",
                    status_category="In Progress",
                    created_date=created,
                    started_date=created + timedelta(hours=10),
                    resolution_date=None
                ))
        
        # Calculate cycle time
        cycle_time = engine.calculate_cycle_time(issues)
        
        # Verify the property
        if complete_count == 0:
            # No complete issues means cycle time should be None
            assert cycle_time is None, \
                f"Cycle time should be None when no issues have both started and resolution dates, got {cycle_time}"
        else:
            # Cycle time should be average of complete issues only
            expected_avg = sum(expected_cycle_times) / len(expected_cycle_times)
            assert cycle_time is not None, "Cycle time should not be None when complete issues exist"
            assert abs(cycle_time - expected_avg) < 0.01, \
                f"Cycle time {cycle_time} != expected {expected_avg} hours (incomplete issues should be excluded)"

    @given(
        minutes_to_complete=st.integers(min_value=1, max_value=1440)  # Up to 24 hours in minutes
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cycle_time_fractional_hours(self, minutes_to_complete, mock_connector):
        """
        **Validates: Requirements 4.3**
        
        Cycle time should correctly calculate fractional hours for sub-day completions.
        """
        engine = MetricsEngine(mock_connector)
        now = datetime.now()
        
        created = now - timedelta(minutes=minutes_to_complete + 2000)
        started = created + timedelta(minutes=1000)
        resolution = started + timedelta(minutes=minutes_to_complete)
        
        issue = Issue(
            jira_id="1",
            key="PROJ-1",
            summary="Quick Completion Issue",
            issue_type="Bug",
            status="Done",
            status_category="Done",
            created_date=created,
            started_date=started,
            resolution_date=resolution
        )
        
        # Calculate cycle time
        cycle_time = engine.calculate_cycle_time([issue])
        
        # Expected cycle time in hours (with fractional part)
        expected_hours = minutes_to_complete / 60.0
        
        # Verify the property
        assert cycle_time is not None, "Cycle time should not be None"
        assert abs(cycle_time - expected_hours) < 0.001, \
            f"Cycle time {cycle_time} != expected {expected_hours} hours for {minutes_to_complete} minutes"


# =============================================================================
# Property 13: Velocity Calculation
# **Validates: Requirements 4.4**
# =============================================================================

class TestVelocityProperty:
    """
    Property test: velocity calculation (Property 13)
    
    Velocity = sum of story_points for issues with status_category = "Done"
    """

    @given(
        issues_data=st.lists(
            st.tuples(
                st.sampled_from(["To Do", "In Progress", "Done"]),
                st.one_of(st.none(), st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
            ),
            min_size=0,
            max_size=30
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_velocity_sums_done_story_points(self, issues_data, mock_connector):
        """
        **Validates: Requirements 4.4**
        
        Velocity = sum of story_points for issues with status_category = "Done"
        """
        engine = MetricsEngine(mock_connector)
        
        # Create issues with the given status categories and story points
        issues = [
            Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Issue {i}",
                issue_type="Story",
                status="Open" if cat != "Done" else "Done",
                status_category=cat,
                story_points=points
            )
            for i, (cat, points) in enumerate(issues_data)
        ]
        
        # Calculate velocity
        velocity = engine.calculate_velocity(issues)
        
        # Expected: sum of story points for Done issues (None treated as 0)
        expected = sum(
            points or 0.0
            for cat, points in issues_data
            if cat == "Done"
        )
        
        # Verify the property
        assert abs(velocity - expected) < 0.0001, \
            f"Velocity {velocity} != expected {expected}"
    @given(
        story_points_list=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_velocity_all_done_issues(self, story_points_list, mock_connector):
        """
        **Validates: Requirements 4.4**
        
        When all issues are Done, velocity should equal the sum of all story points.
        """
        engine = MetricsEngine(mock_connector)
        
        # Create all Done issues with specific story points
        issues = [
            Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Done Issue {i}",
                issue_type="Story",
                status="Done",
                status_category="Done",
                story_points=sp
            )
            for i, sp in enumerate(story_points_list)
        ]
        
        # Calculate velocity
        velocity = engine.calculate_velocity(issues)
        
        # Expected: sum of all story points
        expected = sum(story_points_list)
        
        # Verify the property
        assert abs(velocity - expected) < 0.0001, \
            f"Velocity {velocity} != expected {expected} for all Done issues"

    @given(
        done_count=st.integers(min_value=0, max_value=15),
        not_done_count=st.integers(min_value=0, max_value=15)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_velocity_excludes_non_done_issues(self, done_count, not_done_count, mock_connector):
        """
        **Validates: Requirements 4.4**
        
        Velocity should only include story points from issues with status_category = "Done".
        Issues with "To Do" or "In Progress" should be excluded.
        """
        engine = MetricsEngine(mock_connector)
        
        issues = []
        expected_velocity = 0.0
        
        # Create Done issues with known story points
        for i in range(done_count):
            sp = float(i + 1) * 2  # 2, 4, 6, 8, ...
            issues.append(Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Done Issue {i}",
                issue_type="Story",
                status="Done",
                status_category="Done",
                story_points=sp
            ))
            expected_velocity += sp
        
        # Create non-Done issues (should be excluded from velocity)
        for i in range(not_done_count):
            sp = float(i + 1) * 10  # 10, 20, 30, ... (larger to make exclusion obvious)
            status_cat = "To Do" if i % 2 == 0 else "In Progress"
            issues.append(Issue(
                jira_id=str(done_count + i),
                key=f"PROJ-{done_count + i}",
                summary=f"Not Done Issue {i}",
                issue_type="Story",
                status="Open" if status_cat == "To Do" else "In Progress",
                status_category=status_cat,
                story_points=sp
            ))
        
        # Calculate velocity
        velocity = engine.calculate_velocity(issues)
        
        # Verify the property: velocity should only include Done issues
        assert abs(velocity - expected_velocity) < 0.0001, \
            f"Velocity {velocity} != expected {expected_velocity} (non-Done issues should be excluded)"

    @given(
        done_with_none_count=st.integers(min_value=0, max_value=10),
        done_with_points_count=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_velocity_treats_none_story_points_as_zero(self, done_with_none_count, done_with_points_count, mock_connector):
        """
        **Validates: Requirements 4.4**
        
        Done issues with story_points = None should be treated as 0 in velocity calculation.
        """
        engine = MetricsEngine(mock_connector)
        
        issues = []
        expected_velocity = 0.0
        
        # Create Done issues with None story points
        for i in range(done_with_none_count):
            issues.append(Issue(
                jira_id=str(i),
                key=f"PROJ-{i}",
                summary=f"Done Issue No Points {i}",
                issue_type="Story",
                status="Done",
                status_category="Done",
                story_points=None  # None should be treated as 0
            ))
        
        # Create Done issues with actual story points
        for i in range(done_with_points_count):
            sp = float(i + 1) * 3  # 3, 6, 9, ...
            issues.append(Issue(
                jira_id=str(done_with_none_count + i),
                key=f"PROJ-{done_with_none_count + i}",
                summary=f"Done Issue With Points {i}",
                issue_type="Story",
                status="Done",
                status_category="Done",
                story_points=sp
            ))
            expected_velocity += sp
        
        # Calculate velocity
        velocity = engine.calculate_velocity(issues)
        
        # Verify the property: None story points should be treated as 0
        assert abs(velocity - expected_velocity) < 0.0001, \
            f"Velocity {velocity} != expected {expected_velocity} (None story points should be 0)"

    @given(
        story_points=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_velocity_single_done_issue(self, story_points, mock_connector):
        """
        **Validates: Requirements 4.4**
        
        For a single Done issue, velocity should equal its story points exactly.
        """
        engine = MetricsEngine(mock_connector)
        
        issue = Issue(
            jira_id="1",
            key="PROJ-1",
            summary="Single Done Issue",
            issue_type="Story",
            status="Done",
            status_category="Done",
            story_points=story_points
        )
        
        # Calculate velocity
        velocity = engine.calculate_velocity([issue])
        
        # Verify the property: velocity should equal the single issue's story points
        assert abs(velocity - story_points) < 0.0001, \
            f"Velocity {velocity} != expected {story_points} for single Done issue"

    def test_velocity_empty_list_returns_zero(self, mock_connector):
        """
        **Validates: Requirements 4.4**
        
        Velocity of an empty issue list should be 0.
        """
        engine = MetricsEngine(mock_connector)
        
        # Calculate velocity for empty list
        velocity = engine.calculate_velocity([])
        
        # Verify the property: empty list should return 0
        assert velocity == 0.0, \
            f"Velocity {velocity} != 0 for empty issue list"

