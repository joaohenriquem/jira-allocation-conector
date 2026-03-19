"""
Unit tests for JiraConnector.

Tests cover:
- Authentication (API Token and PAT)
- test_connection() with success and failure
- get_projects() with mocked responses
- get_issues() with pagination
- Retry with backoff for rate limiting (HTTP 429)

Uses responses library for HTTP mocking.
"""

import time
from unittest.mock import patch, MagicMock

import pytest
import responses
from requests.exceptions import ConnectionError, Timeout

from src.connector.jira_connector import JiraConnector, PaginatedIssues
from src.models.data_models import JiraConfig


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def api_token_config():
    """Create a JiraConfig for API Token authentication."""
    return JiraConfig(
        base_url="https://test.atlassian.net",
        auth_type="api_token",
        username="user@test.com",
        api_token="test-api-token"
    )


@pytest.fixture
def pat_config():
    """Create a JiraConfig for PAT authentication."""
    return JiraConfig(
        base_url="https://jira.company.com",
        auth_type="pat",
        personal_access_token="test-pat-token"
    )


@pytest.fixture
def sample_user_info():
    """Sample user info response from Jira API."""
    return {
        "accountId": "123456",
        "displayName": "Test User",
        "emailAddress": "user@test.com"
    }


@pytest.fixture
def sample_server_info():
    """Sample server info response from Jira API."""
    return {
        "serverTitle": "Test Jira",
        "version": "9.0.0",
        "baseUrl": "https://test.atlassian.net"
    }


@pytest.fixture
def sample_project():
    """Sample project response from Jira API."""
    return {
        "id": "10001",
        "key": "PROJ",
        "name": "Test Project",
        "description": "A test project",
        "lead": {"accountId": "lead-123"}
    }


@pytest.fixture
def sample_issues_response():
    """Sample issues search response from Jira API."""
    return {
        "startAt": 0,
        "maxResults": 50,
        "total": 2,
        "issues": [
            {
                "id": "10001",
                "key": "PROJ-1",
                "fields": {
                    "summary": "Test Issue 1",
                    "issuetype": {"name": "Story"},
                    "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
                    "assignee": {"accountId": "user-1", "displayName": "User One"},
                    "customfield_10016": 5.0,
                    "labels": ["backend"],
                    "components": [{"name": "API"}],
                    "created": "2024-01-15T10:00:00.000+0000"
                }
            },
            {
                "id": "10002",
                "key": "PROJ-2",
                "fields": {
                    "summary": "Test Issue 2",
                    "issuetype": {"name": "Bug"},
                    "status": {"name": "Done", "statusCategory": {"name": "Done"}},
                    "assignee": {"accountId": "user-2", "displayName": "User Two"},
                    "customfield_10016": 3.0,
                    "labels": ["frontend"],
                    "components": [],
                    "created": "2024-01-16T10:00:00.000+0000",
                    "resolutiondate": "2024-01-18T15:00:00.000+0000"
                }
            }
        ]
    }


# =============================================================================
# Authentication Tests
# =============================================================================

class TestJiraConnectorAuthentication:
    """Tests for JiraConnector authentication setup."""

    def test_api_token_auth_setup(self, api_token_config):
        """Test that API Token authentication is configured correctly."""
        connector = JiraConnector(api_token_config)
        
        assert connector._session.auth is not None
        assert "Accept" in connector._session.headers
        assert connector._session.headers["Accept"] == "application/json"

    def test_pat_auth_setup(self, pat_config):
        """Test that PAT authentication is configured correctly."""
        connector = JiraConnector(pat_config)
        
        assert "Authorization" in connector._session.headers
        assert connector._session.headers["Authorization"] == "Bearer test-pat-token"

    def test_api_token_auth_missing_username_raises_error(self):
        """Test that missing username for API Token auth raises ValueError."""
        config = JiraConfig(
            base_url="https://test.atlassian.net",
            auth_type="api_token",
            api_token="test-token"
        )
        
        with pytest.raises(ValueError) as exc_info:
            JiraConnector(config)
        
        assert "API Token auth requires username and api_token" in str(exc_info.value)

    def test_api_token_auth_missing_token_raises_error(self):
        """Test that missing API token raises ValueError."""
        config = JiraConfig(
            base_url="https://test.atlassian.net",
            auth_type="api_token",
            username="user@test.com"
        )
        
        with pytest.raises(ValueError) as exc_info:
            JiraConnector(config)
        
        assert "API Token auth requires username and api_token" in str(exc_info.value)

    def test_pat_auth_missing_token_raises_error(self):
        """Test that missing PAT raises ValueError."""
        config = JiraConfig(
            base_url="https://test.atlassian.net",
            auth_type="pat"
        )
        
        with pytest.raises(ValueError) as exc_info:
            JiraConnector(config)
        
        assert "PAT auth requires personal_access_token" in str(exc_info.value)

    def test_unsupported_auth_type_raises_error(self):
        """Test that unsupported auth type raises ValueError."""
        config = JiraConfig(
            base_url="https://test.atlassian.net",
            auth_type="oauth"  # type: ignore
        )
        
        with pytest.raises(ValueError) as exc_info:
            JiraConnector(config)
        
        assert "Unsupported auth_type" in str(exc_info.value)

    @responses.activate
    def test_authenticate_success(self, api_token_config, sample_user_info):
        """Test successful authentication."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/myself",
            json=sample_user_info,
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        result = connector.authenticate()
        
        assert result.success is True
        assert result.user_info == sample_user_info
        assert result.error_message is None

    @responses.activate
    def test_authenticate_invalid_credentials(self, api_token_config):
        """Test authentication with invalid credentials."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/myself",
            status=401
        )
        
        connector = JiraConnector(api_token_config)
        result = connector.authenticate()
        
        assert result.success is False
        assert "Invalid credentials" in result.error_message

    @responses.activate
    def test_authenticate_forbidden(self, api_token_config):
        """Test authentication with forbidden access."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/myself",
            status=403
        )
        
        connector = JiraConnector(api_token_config)
        result = connector.authenticate()
        
        assert result.success is False
        assert "Access forbidden" in result.error_message


# =============================================================================
# Connection Tests
# =============================================================================

class TestJiraConnectorTestConnection:
    """Tests for test_connection() method."""

    @responses.activate
    def test_connection_success(self, api_token_config, sample_server_info):
        """Test successful connection test."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            json=sample_server_info,
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        status = connector.test_connection()
        
        assert status.connected is True
        assert status.server_info == sample_server_info
        assert status.error_message is None

    @responses.activate
    def test_connection_unauthorized(self, api_token_config):
        """Test connection with unauthorized credentials."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            status=401
        )
        
        connector = JiraConnector(api_token_config)
        status = connector.test_connection()
        
        assert status.connected is False
        assert "Unauthorized" in status.error_message

    @responses.activate
    def test_connection_forbidden(self, api_token_config):
        """Test connection with forbidden access."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            status=403
        )
        
        connector = JiraConnector(api_token_config)
        status = connector.test_connection()
        
        assert status.connected is False
        assert "Forbidden" in status.error_message

    @responses.activate
    def test_connection_server_error(self, api_token_config):
        """Test connection with server error."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            status=500
        )
        
        connector = JiraConnector(api_token_config)
        status = connector.test_connection()
        
        assert status.connected is False
        assert "HTTP 500" in status.error_message

    def test_connection_network_error(self, api_token_config):
        """Test connection with network error."""
        connector = JiraConnector(api_token_config)
        
        with patch.object(connector._session, 'request', side_effect=ConnectionError("Network unreachable")):
            status = connector.test_connection()
        
        assert status.connected is False
        assert "Connection error" in status.error_message

    def test_connection_timeout(self, api_token_config):
        """Test connection with timeout."""
        connector = JiraConnector(api_token_config)
        
        with patch.object(connector._session, 'request', side_effect=Timeout("Request timed out")):
            status = connector.test_connection()
        
        assert status.connected is False
        assert "timeout" in status.error_message.lower()


# =============================================================================
# Project Tests
# =============================================================================

class TestJiraConnectorGetProjects:
    """Tests for get_projects() method."""

    @responses.activate
    def test_get_projects_success(self, api_token_config, sample_project):
        """Test successful project retrieval."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/project/PROJ",
            json=sample_project,
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        projects = connector.get_projects(["PROJ"])
        
        assert len(projects) == 1
        assert projects[0].key == "PROJ"
        assert projects[0].name == "Test Project"
        assert projects[0].jira_id == "10001"

    @responses.activate
    def test_get_projects_multiple(self, api_token_config):
        """Test retrieving multiple projects."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/project/PROJ1",
            json={"id": "1", "key": "PROJ1", "name": "Project 1"},
            status=200
        )
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/project/PROJ2",
            json={"id": "2", "key": "PROJ2", "name": "Project 2"},
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        projects = connector.get_projects(["PROJ1", "PROJ2"])
        
        assert len(projects) == 2
        assert projects[0].key == "PROJ1"
        assert projects[1].key == "PROJ2"

    @responses.activate
    def test_get_projects_not_found(self, api_token_config):
        """Test project not found error."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/project/INVALID",
            status=404
        )
        
        connector = JiraConnector(api_token_config)
        
        with pytest.raises(ValueError) as exc_info:
            connector.get_projects(["INVALID"])
        
        assert "does not exist" in str(exc_info.value)

    @responses.activate
    def test_get_projects_forbidden(self, api_token_config):
        """Test project access forbidden."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/project/SECRET",
            status=403
        )
        
        connector = JiraConnector(api_token_config)
        
        with pytest.raises(ValueError) as exc_info:
            connector.get_projects(["SECRET"])
        
        assert "No permission" in str(exc_info.value)


# =============================================================================
# Issues Tests
# =============================================================================

class TestJiraConnectorGetIssues:
    """Tests for get_issues() method."""

    @responses.activate
    def test_get_issues_success(self, api_token_config, sample_issues_response):
        """Test successful issues retrieval."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search",
            json=sample_issues_response,
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        result = connector.get_issues(
            jql="project = PROJ",
            fields=["summary", "status", "assignee"]
        )
        
        assert isinstance(result, PaginatedIssues)
        assert len(result.issues) == 2
        assert result.total == 2
        assert result.issues[0].key == "PROJ-1"
        assert result.issues[1].key == "PROJ-2"

    @responses.activate
    def test_get_issues_with_pagination(self, api_token_config):
        """Test issues retrieval with pagination."""
        # First page
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search",
            json={
                "startAt": 0,
                "maxResults": 50,
                "total": 100,
                "issues": [{"id": "1", "key": "PROJ-1", "fields": {
                    "summary": "Issue 1", "issuetype": {"name": "Story"},
                    "status": {"name": "Open", "statusCategory": {"name": "To Do"}},
                    "created": "2024-01-15T10:00:00.000+0000"
                }}]
            },
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        result = connector.get_issues(jql="project = PROJ", fields=["summary"], start_at=0)
        
        assert result.start_at == 0
        assert result.total == 100
        assert result.has_more is True

    @responses.activate
    def test_get_issues_invalid_jql(self, api_token_config):
        """Test issues retrieval with invalid JQL."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search",
            json={"errorMessages": ["Invalid JQL query"]},
            status=400
        )
        
        connector = JiraConnector(api_token_config)
        
        with pytest.raises(ValueError) as exc_info:
            connector.get_issues(jql="invalid jql !!!", fields=["summary"])
        
        assert "Invalid JQL" in str(exc_info.value)

    @responses.activate
    def test_get_issues_parses_fields_correctly(self, api_token_config, sample_issues_response):
        """Test that issue fields are parsed correctly."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search",
            json=sample_issues_response,
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        result = connector.get_issues(jql="project = PROJ", fields=["summary", "status"])
        
        issue1 = result.issues[0]
        assert issue1.summary == "Test Issue 1"
        assert issue1.issue_type == "Story"
        assert issue1.status == "In Progress"
        assert issue1.status_category == "In Progress"
        assert issue1.assignee_account_id == "user-1"
        assert issue1.assignee_name == "User One"
        assert issue1.story_points == 5.0
        assert "backend" in issue1.labels
        assert "API" in issue1.components


# =============================================================================
# Retry and Rate Limiting Tests
# =============================================================================

class TestJiraConnectorRetry:
    """Tests for retry with backoff for rate limiting."""

    @responses.activate
    def test_retry_on_rate_limit_429(self, api_token_config, sample_server_info):
        """Test retry with backoff on HTTP 429 rate limiting."""
        # First request returns 429, second succeeds
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            status=429,
            headers={"Retry-After": "1"}
        )
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            json=sample_server_info,
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        
        with patch('time.sleep'):  # Skip actual sleep
            status = connector.test_connection()
        
        assert status.connected is True
        assert len(responses.calls) == 2

    @responses.activate
    def test_retry_exhausted_on_rate_limit(self, api_token_config):
        """Test that retries are exhausted after max attempts."""
        # All requests return 429
        for _ in range(4):  # MAX_RETRIES + 1
            responses.add(
                responses.GET,
                "https://test.atlassian.net/rest/api/3/serverInfo",
                status=429,
                headers={"Retry-After": "1"}
            )
        
        connector = JiraConnector(api_token_config)
        
        with patch('time.sleep'):  # Skip actual sleep
            status = connector.test_connection()
        
        assert status.connected is False

    @responses.activate
    def test_retry_on_connection_error(self, api_token_config, sample_server_info):
        """Test retry on connection error."""
        connector = JiraConnector(api_token_config)
        
        call_count = 0
        original_request = connector._session.request
        
        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            # Return a mock response for the third call
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_server_info
            return mock_response
        
        with patch.object(connector._session, 'request', side_effect=mock_request):
            with patch('time.sleep'):  # Skip actual sleep
                status = connector.test_connection()
        
        assert status.connected is True
        assert call_count == 3

    @responses.activate
    def test_exponential_backoff_timing(self, api_token_config, sample_server_info):
        """Test that exponential backoff increases wait time."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            status=429,
            headers={"Retry-After": "1"}
        )
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            status=429
        )
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            json=sample_server_info,
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        sleep_times = []
        
        with patch('time.sleep', side_effect=lambda x: sleep_times.append(x)):
            status = connector.test_connection()
        
        assert status.connected is True
        # First retry uses Retry-After header (1), second uses backoff (2)
        assert len(sleep_times) == 2
        assert sleep_times[0] == 1  # From Retry-After header
        assert sleep_times[1] == 2  # Exponential backoff


# =============================================================================
# Edge Cases
# =============================================================================

class TestJiraConnectorEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_base_url_trailing_slash_removed(self, api_token_config):
        """Test that trailing slash is removed from base URL."""
        config = JiraConfig(
            base_url="https://test.atlassian.net/",
            auth_type="api_token",
            username="user@test.com",
            api_token="token"
        )
        connector = JiraConnector(config)
        
        assert connector.base_url == "https://test.atlassian.net"

    @responses.activate
    def test_get_issues_handles_null_fields(self, api_token_config):
        """Test that null fields in issues are handled gracefully."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search",
            json={
                "startAt": 0,
                "maxResults": 50,
                "total": 1,
                "issues": [{
                    "id": "1",
                    "key": "PROJ-1",
                    "fields": {
                        "summary": "Issue with nulls",
                        "issuetype": {"name": "Story"},
                        "status": {"name": "Open", "statusCategory": {"name": "To Do"}},
                        "assignee": None,
                        "customfield_10016": None,
                        "labels": None,
                        "components": None,
                        "created": "2024-01-15T10:00:00.000+0000"
                    }
                }]
            },
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        result = connector.get_issues(jql="project = PROJ", fields=["summary"])
        
        issue = result.issues[0]
        assert issue.assignee_account_id is None
        assert issue.assignee_name is None
        assert issue.story_points is None
        assert issue.labels == []
        assert issue.components == []

    @responses.activate
    def test_paginated_issues_has_more_property(self, api_token_config):
        """Test PaginatedIssues.has_more property."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search",
            json={
                "startAt": 0,
                "maxResults": 50,
                "total": 50,
                "issues": [{"id": str(i), "key": f"PROJ-{i}", "fields": {
                    "summary": f"Issue {i}", "issuetype": {"name": "Story"},
                    "status": {"name": "Open", "statusCategory": {"name": "To Do"}},
                    "created": "2024-01-15T10:00:00.000+0000"
                }} for i in range(50)]
            },
            status=200
        )
        
        connector = JiraConnector(api_token_config)
        result = connector.get_issues(jql="project = PROJ", fields=["summary"])
        
        # 50 issues returned, 50 total - no more pages
        assert result.has_more is False
