"""
Jira Connector Module.

This module provides the JiraConnector class for communicating with the Jira API.
Supports both Jira Cloud (API Token) and Jira Server/Data Center (PAT) authentication.
"""

import time
import os
from typing import List, Optional

import requests
from requests.auth import HTTPBasicAuth

from ..models.data_models import (
    AuthResult,
    ConnectionStatus,
    JiraConfig,
    Project,
    Sprint,
    Issue,
)
from ..utils.logging import get_logger, log_auth_error, log_api_error, log_rate_limit, log_request

logger = get_logger(__name__)


class PaginatedIssues:
    """Container for paginated issue results."""
    
    def __init__(
        self,
        issues: List[Issue],
        start_at: int,
        max_results: int,
        total: int
    ):
        self.issues = issues
        self.start_at = start_at
        self.max_results = max_results
        self.total = total
    
    @property
    def has_more(self) -> bool:
        """Check if there are more results to fetch."""
        return self.start_at + len(self.issues) < self.total


class JiraConnector:
    """
    Connector for Jira API communication.
    
    Supports:
    - API Token authentication (Jira Cloud) - Basic Auth with email:api_token
    - PAT authentication (Jira Server/Data Center) - Bearer token
    
    Implements retry with exponential backoff for rate limiting (HTTP 429).
    """
    
    MAX_RETRIES = 3
    INITIAL_BACKOFF_SECONDS = 1
    DEFAULT_PAGE_SIZE = 50
    
    def __init__(self, config: JiraConfig):
        """
        Initialize connector with authentication configuration.
        
        Args:
            config: JiraConfig with base_url and authentication credentials
        """
        self.config = config
        self.base_url = config.base_url.rstrip('/')
        self._session = requests.Session()
        self._setup_authentication()
    
    def _setup_authentication(self) -> None:
        """Configure session authentication based on auth_type."""
        if self.config.auth_type == "api_token":
            # Jira Cloud: Basic Auth with email:api_token
            if not self.config.username or not self.config.api_token:
                raise ValueError("API Token auth requires username and api_token")
            self._session.auth = HTTPBasicAuth(
                self.config.username,
                self.config.api_token
            )
        elif self.config.auth_type == "pat":
            # Jira Server/Data Center: Bearer token
            if not self.config.personal_access_token:
                raise ValueError("PAT auth requires personal_access_token")
            self._session.headers.update({
                "Authorization": f"Bearer {self.config.personal_access_token}"
            })
        else:
            raise ValueError(f"Unsupported auth_type: {self.config.auth_type}")
        
        # Common headers
        self._session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        # Configure proxy settings
        self._setup_proxy()

    def _setup_proxy(self) -> None:
        """Configure proxy settings from environment variables."""
        no_proxy = os.getenv("NO_PROXY", "").lower()
        
        if no_proxy == "true" or no_proxy == "1":
            # Bypass proxy entirely
            self._session.trust_env = False
            self._session.proxies = {"http": None, "https": None}
            logger.debug("proxy_disabled", reason="NO_PROXY=true")
        else:
            # Use configured proxy or system settings
            http_proxy = os.getenv("HTTP_PROXY", "")
            https_proxy = os.getenv("HTTPS_PROXY", "")
            
            if http_proxy or https_proxy:
                self._session.proxies = {}
                if http_proxy:
                    self._session.proxies["http"] = http_proxy
                if https_proxy:
                    self._session.proxies["https"] = https_proxy
                logger.debug("proxy_configured", http=http_proxy, https=https_proxy)
            else:
                # Use system proxy settings (default behavior)
                self._session.trust_env = True
        
        # Configure SSL verification
        ssl_verify = os.getenv("SSL_VERIFY", "true").lower()
        if ssl_verify == "false" or ssl_verify == "0":
            self._session.verify = False
            # Suppress SSL warnings when verification is disabled
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            logger.warning("ssl_verification_disabled", reason="SSL_VERIFY=false")

    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None
    ) -> requests.Response:
        """
        Make HTTP request with exponential backoff retry for rate limiting.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (will be appended to base_url)
            params: Query parameters
            json_data: JSON body data
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If all retries fail
        """
        url = f"{self.base_url}{endpoint}"
        backoff = self.INITIAL_BACKOFF_SECONDS
        last_exception = None
        
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=30
                )
                
                # Handle rate limiting (HTTP 429)
                if response.status_code == 429:
                    if attempt < self.MAX_RETRIES:
                        # Check for Retry-After header
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            wait_time = int(retry_after)
                        else:
                            wait_time = backoff
                        
                        log_rate_limit(
                            logger,
                            retry_after=wait_time,
                            attempt=attempt + 1,
                            max_retries=self.MAX_RETRIES,
                            endpoint=endpoint
                        )
                        time.sleep(wait_time)
                        backoff *= 2  # Exponential backoff: 1s, 2s, 4s
                        continue
                    else:
                        # Max retries reached
                        response.raise_for_status()
                
                return response
                
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < self.MAX_RETRIES:
                    logger.warning(
                        "connection_error",
                        retry_in_seconds=backoff,
                        attempt=attempt + 1,
                        max_retries=self.MAX_RETRIES,
                        endpoint=endpoint
                    )
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.MAX_RETRIES:
                    logger.warning(
                        "request_timeout",
                        retry_in_seconds=backoff,
                        attempt=attempt + 1,
                        max_retries=self.MAX_RETRIES,
                        endpoint=endpoint
                    )
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise requests.RequestException("Max retries exceeded")
    
    def authenticate(self) -> AuthResult:
        """
        Validate credentials and establish connection.
        
        Returns:
            AuthResult with success status and user info or error message
        """
        try:
            response = self._request_with_retry("GET", "/rest/api/2/myself")
            
            if response.status_code == 200:
                user_info = response.json()
                logger.info(
                    "auth_success",
                    user=user_info.get('displayName', 'Unknown'),
                    account_id=user_info.get('accountId')
                )
                return AuthResult(
                    success=True,
                    user_info=user_info
                )
            elif response.status_code == 401:
                error_msg = "Authentication failed: Invalid credentials. Please check your username and API token/PAT."
                log_auth_error(logger, error_msg, status_code=401)
                return AuthResult(
                    success=False,
                    error_message=error_msg
                )
            elif response.status_code == 403:
                error_msg = "Authentication failed: Access forbidden. Please check your permissions."
                log_auth_error(logger, error_msg, status_code=403)
                return AuthResult(
                    success=False,
                    error_message=error_msg
                )
            else:
                error_msg = f"Authentication failed: HTTP {response.status_code}"
                log_auth_error(logger, error_msg, status_code=response.status_code)
                return AuthResult(
                    success=False,
                    error_message=error_msg
                )
                
        except requests.exceptions.ConnectionError:
            error_msg = f"Connection error: Unable to connect to {self.base_url}. Please check the URL."
            log_auth_error(logger, error_msg, base_url=self.base_url)
            return AuthResult(
                success=False,
                error_message=error_msg
            )
        except requests.exceptions.Timeout:
            error_msg = "Connection timeout: The server took too long to respond."
            log_auth_error(logger, error_msg, base_url=self.base_url)
            return AuthResult(
                success=False,
                error_message=error_msg
            )
        except requests.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            log_auth_error(logger, error_msg, exception=str(e))
            return AuthResult(
                success=False,
                error_message=error_msg
            )
    
    def test_connection(self) -> ConnectionStatus:
        """
        Test connectivity with Jira.
        
        Returns:
            ConnectionStatus with connection state and server info
        """
        try:
            response = self._request_with_retry("GET", "/rest/api/2/serverInfo")
            
            if response.status_code == 200:
                server_info = response.json()
                logger.info(
                    "connection_established",
                    server=server_info.get('serverTitle', 'Unknown'),
                    version=server_info.get('version')
                )
                return ConnectionStatus(
                    connected=True,
                    server_info=server_info
                )
            elif response.status_code == 401:
                error_msg = "Unauthorized: Invalid credentials"
                log_auth_error(logger, error_msg, status_code=401)
                return ConnectionStatus(
                    connected=False,
                    error_message=error_msg
                )
            elif response.status_code == 403:
                error_msg = "Forbidden: Insufficient permissions to access server info"
                log_auth_error(logger, error_msg, status_code=403)
                return ConnectionStatus(
                    connected=False,
                    error_message=error_msg
                )
            else:
                error_msg = f"Connection test failed: HTTP {response.status_code}"
                log_api_error(logger, "/rest/api/2/serverInfo", response.status_code, error_msg)
                return ConnectionStatus(
                    connected=False,
                    error_message=error_msg
                )
                
        except requests.exceptions.ConnectionError:
            error_msg = f"Connection error: Unable to reach {self.base_url}"
            logger.error("connection_failed", error=error_msg, base_url=self.base_url)
            return ConnectionStatus(
                connected=False,
                error_message=error_msg
            )
        except requests.exceptions.Timeout:
            error_msg = "Connection timeout: Server did not respond in time"
            logger.error("connection_timeout", error=error_msg, base_url=self.base_url)
            return ConnectionStatus(
                connected=False,
                error_message=error_msg
            )
        except requests.RequestException as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error("connection_error", error=error_msg, exception=str(e))
            return ConnectionStatus(
                connected=False,
                error_message=error_msg
            )

    def get_boards(self, project_key: Optional[str] = None) -> List[dict]:
        """
        Get available boards, optionally filtered by project.
        
        Args:
            project_key: Optional project key to filter boards
            
        Returns:
            List of board dictionaries with id and name
        """
        try:
            params = {"maxResults": 50}
            if project_key:
                params["projectKeyOrId"] = project_key
            
            response = self._request_with_retry(
                "GET",
                "/rest/agile/1.0/board",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                boards = [
                    {"id": b.get("id"), "name": b.get("name"), "type": b.get("type")}
                    for b in data.get("values", [])
                ]
                logger.debug("boards_fetched", count=len(boards))
                return boards
            else:
                logger.warning("boards_fetch_failed", status_code=response.status_code)
                return []
        except Exception as e:
            logger.warning("boards_fetch_error", error=str(e))
            return []

    def get_board_issues(self, board_id: int, fields: List[str], jql_extra: str = None, next_page_token: str = None) -> 'PaginatedIssues':
        """
        Get issues from a specific board using the Agile API.
        This returns all issues visible on the board, regardless of project.
        
        Args:
            board_id: The board ID
            fields: List of fields to retrieve
            jql_extra: Additional JQL to filter (appended with AND)
            next_page_token: Token for pagination
            
        Returns:
            PaginatedIssues with issues and pagination info
        """
        try:
            params = {
                "maxResults": self.DEFAULT_PAGE_SIZE,
                "fields": ",".join(fields)
            }
            if jql_extra:
                params["jql"] = jql_extra
            if next_page_token:
                params["startAt"] = int(next_page_token)
            
            response = self._request_with_retry(
                "GET",
                f"/rest/agile/1.0/board/{board_id}/issue",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                issues = []
                for item in data.get("issues", []):
                    issue = self._parse_issue(item)
                    issues.append(issue)
                
                total = data.get("total", 0)
                start_at = data.get("startAt", 0)
                max_results = data.get("maxResults", self.DEFAULT_PAGE_SIZE)
                is_last = (start_at + len(issues)) >= total
                
                logger.debug("board_issues_fetched", board_id=board_id, count=len(issues), total=total)
                
                result = PaginatedIssues(
                    issues=issues,
                    start_at=start_at,
                    max_results=max_results,
                    total=total
                )
                result.is_last = is_last
                result.next_page_token = str(start_at + len(issues)) if not is_last else None
                return result
            else:
                raise ValueError(f"Failed to get board issues: HTTP {response.status_code}")
        except requests.exceptions.ConnectionError:
            raise ValueError("Connection error while fetching board issues")
        except requests.exceptions.Timeout:
            raise ValueError("Timeout while fetching board issues")

    def get_projects(self, project_keys: List[str]) -> List[Project]:
        """
        Extract data from configured projects.
        If project_keys is empty, fetch all accessible projects.
        
        Args:
            project_keys: List of project keys to fetch (empty = all projects)
            
        Returns:
            List of Project objects
            
        Raises:
            ValueError: If a project is not found or access is denied
        """
        projects = []
        
        # If no specific keys provided, fetch all projects
        if not project_keys:
            return self.get_all_projects()
        
        for key in project_keys:
            try:
                response = self._request_with_retry(
                    "GET",
                    f"/rest/api/2/project/{key}"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    project = Project(
                        jira_id=data.get("id", ""),
                        key=data.get("key", ""),
                        name=data.get("name", ""),
                        description=data.get("description"),
                        lead_account_id=data.get("lead", {}).get("accountId")
                    )
                    projects.append(project)
                    logger.debug("project_fetched", project_key=key, project_name=data.get("name", ""))
                    
                elif response.status_code == 401:
                    raise ValueError(
                        f"Unauthorized: Invalid credentials when accessing project '{key}'"
                    )
                elif response.status_code == 403:
                    raise ValueError(
                        f"Forbidden: No permission to access project '{key}'"
                    )
                elif response.status_code == 404:
                    raise ValueError(
                        f"Not found: Project '{key}' does not exist"
                    )
                else:
                    raise ValueError(
                        f"Failed to fetch project '{key}': HTTP {response.status_code}"
                    )
                    
            except requests.exceptions.ConnectionError:
                raise ValueError(
                    f"Connection error while fetching project '{key}'"
                )
            except requests.exceptions.Timeout:
                raise ValueError(
                    f"Timeout while fetching project '{key}'"
                )
        
        return projects

    def get_all_projects(self) -> List[Project]:
        """
        Fetch all accessible projects from Jira.
        
        Uses /rest/api/2/project which returns all projects the user has access to.
        
        Returns:
            List of Project objects
        """
        projects = []
        
        try:
            # Use simple /rest/api/2/project endpoint (returns all accessible projects)
            response = self._request_with_retry(
                "GET",
                "/rest/api/2/project"
            )
            
            logger.info("projects_api_response", 
                       status_code=response.status_code,
                       content_length=len(response.text))
            
            if response.status_code == 200:
                data = response.json()
                
                logger.info("projects_data_received", 
                           data_type=type(data).__name__,
                           count=len(data) if isinstance(data, list) else "not_a_list")
                
                # This endpoint returns a list directly, not paginated
                if isinstance(data, list):
                    for item in data:
                        project = Project(
                            jira_id=item.get("id", ""),
                            key=item.get("key", ""),
                            name=item.get("name", ""),
                            description=item.get("description"),
                            lead_account_id=item.get("lead", {}).get("accountId") if item.get("lead") else None
                        )
                        projects.append(project)
                        logger.debug("project_parsed", key=item.get("key"), name=item.get("name"))
                else:
                    logger.warning("unexpected_response_format", data_keys=list(data.keys()) if isinstance(data, dict) else "unknown")
                
                logger.info("all_projects_fetched", count=len(projects))
            else:
                logger.warning("projects_fetch_failed", 
                              status_code=response.status_code,
                              response_text=response.text[:500])
                
        except Exception as e:
            logger.warning("projects_fetch_error", error=str(e))
        
        return projects
    
    def get_sprints(
        self,
        board_id: int,
        state: str = "active,closed"
    ) -> List[Sprint]:
        """
        Extract sprints from a board.
        
        Args:
            board_id: Jira board ID
            state: Comma-separated sprint states to filter (future, active, closed)
            
        Returns:
            List of Sprint objects
        """
        sprints = []
        start_at = 0
        
        while True:
            try:
                response = self._request_with_retry(
                    "GET",
                    f"/rest/agile/1.0/board/{board_id}/sprint",
                    params={
                        "state": state,
                        "startAt": start_at,
                        "maxResults": self.DEFAULT_PAGE_SIZE
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    values = data.get("values", [])
                    
                    for item in values:
                        sprint = Sprint(
                            jira_id=item.get("id", 0),
                            name=item.get("name", ""),
                            state=item.get("state", "future"),
                            board_id=board_id,
                            start_date=self._parse_datetime(item.get("startDate")),
                            end_date=self._parse_datetime(item.get("endDate")),
                            complete_date=self._parse_datetime(item.get("completeDate")),
                            goal=item.get("goal")
                        )
                        sprints.append(sprint)
                    
                    # Check if there are more results
                    if data.get("isLast", True) or len(values) < self.DEFAULT_PAGE_SIZE:
                        break
                    
                    start_at += len(values)
                    
                elif response.status_code == 401:
                    raise ValueError("Unauthorized: Invalid credentials")
                elif response.status_code == 403:
                    raise ValueError(
                        f"Forbidden: No permission to access board {board_id}"
                    )
                elif response.status_code == 404:
                    raise ValueError(
                        f"Not found: Board {board_id} does not exist"
                    )
                else:
                    raise ValueError(
                        f"Failed to fetch sprints: HTTP {response.status_code}"
                    )
                    
            except requests.exceptions.ConnectionError:
                raise ValueError(
                    f"Connection error while fetching sprints for board {board_id}"
                )
            except requests.exceptions.Timeout:
                raise ValueError(
                    f"Timeout while fetching sprints for board {board_id}"
                )
        
        logger.debug("sprints_fetched", board_id=board_id, count=len(sprints))
        return sprints
    
    def get_issues(
        self,
        jql: str,
        fields: List[str],
        start_at: int = 0,
        next_page_token: str = None
    ) -> PaginatedIssues:
        """
        Extract issues with pagination and JQL.

        Uses the new Jira Cloud /rest/api/3/search/jql endpoint which
        paginates via nextPageToken/isLast instead of total/startAt.

        Args:
            jql: JQL query string
            fields: List of fields to retrieve
            start_at: Starting index (kept for compatibility)
            next_page_token: Token for next page (new API)

        Returns:
            PaginatedIssues with issues and pagination info
        """
        try:
            params = {
                "jql": jql,
                "maxResults": self.DEFAULT_PAGE_SIZE,
                "fields": ",".join(fields)
            }

            if next_page_token:
                params["nextPageToken"] = next_page_token

            response = self._request_with_retry(
                "GET",
                "/rest/api/3/search/jql",
                params=params
            )

            if response.status_code == 200:
                data = response.json()
                issues = []

                for item in data.get("issues", []):
                    issue = self._parse_issue(item)
                    issues.append(issue)

                is_last = data.get("isLast", True)
                token = data.get("nextPageToken")

                logger.debug(
                    "issues_fetched",
                    count=len(issues),
                    is_last=is_last,
                    has_next_token=bool(token)
                )

                result = PaginatedIssues(
                    issues=issues,
                    start_at=start_at,
                    max_results=self.DEFAULT_PAGE_SIZE,
                    total=0  # Not provided by new API
                )
                # Store pagination state on the result
                result.is_last = is_last
                result.next_page_token = token

                return result

            elif response.status_code == 400:
                error_msg = response.json().get("errorMessages", ["Invalid JQL"])
                raise ValueError(f"Invalid JQL query: {error_msg}")
            elif response.status_code == 401:
                raise ValueError("Unauthorized: Invalid credentials")
            elif response.status_code == 403:
                raise ValueError("Forbidden: No permission to search issues")
            else:
                raise ValueError(
                    f"Failed to search issues: HTTP {response.status_code}"
                )

        except requests.exceptions.ConnectionError:
            raise ValueError("Connection error while searching issues")
        except requests.exceptions.Timeout:
            raise ValueError("Timeout while searching issues")


    def _parse_issue(self, data: dict) -> Issue:
        """
        Parse issue data from Jira API response.
        
        Args:
            data: Raw issue data from API
            
        Returns:
            Issue object
        """
        fields = data.get("fields", {})
        
        # Parse assignee
        assignee = fields.get("assignee") or {}
        assignee_account_id = assignee.get("accountId")
        assignee_name = assignee.get("displayName")
        
        # Parse status
        status_obj = fields.get("status") or {}
        status = status_obj.get("name", "Unknown")
        status_category_obj = status_obj.get("statusCategory") or {}
        status_category_name = status_category_obj.get("name", "To Do")
        
        # Map status category to our enum values (supports English and Portuguese)
        status_category_map = {
            # English
            "To Do": "To Do",
            "In Progress": "In Progress",
            "Done": "Done",
            # Portuguese (Jira BR)
            "Itens Pendentes": "To Do",
            "Em andamento": "In Progress",
            "Itens concluídos": "Done",
            "A Fazer": "To Do",
            "Concluído": "Done",
        }
        status_category = status_category_map.get(status_category_name, "To Do")
        
        # Parse T-Shirt Size (primary field for complexity estimation)
        t_shirt_size = None
        # Try common T-Shirt Size field names
        for field_name in ["customfield_11891", "customfield_10371", "customfield_10117", "customfield_10025", "tShirtSize"]:
            if field_name in fields and fields[field_name] is not None:
                field_value = fields[field_name]
                # Handle both string and object formats
                if isinstance(field_value, dict):
                    t_shirt_size = field_value.get("value") or field_value.get("name")
                else:
                    t_shirt_size = str(field_value)
                if t_shirt_size:
                    break
        
        # Parse story points (fallback - will be calculated from T-Shirt Size if not present)
        story_points = None
        # Try common story points field names (order matters - most common first)
        for field_name in ["customfield_10370", "customfield_10016", "customfield_10026", "storyPoints"]:
            if field_name in fields and fields[field_name] is not None:
                try:
                    story_points = float(fields[field_name])
                    break
                except (ValueError, TypeError):
                    continue
        
        # Parse labels and components
        labels = fields.get("labels", []) or []
        components = [c.get("name", "") for c in (fields.get("components") or [])]
        
        # Parse issue type
        issue_type_obj = fields.get("issuetype") or {}
        issue_type = issue_type_obj.get("name", "Unknown")
        
        _issue_key = data.get("key", "")
        _project_key = _issue_key.split("-")[0] if "-" in _issue_key else None
        
        return Issue(
            jira_id=data.get("id", ""),
            key=_issue_key,
            summary=fields.get("summary", ""),
            issue_type=issue_type,
            status=status,
            status_category=status_category,
            assignee_account_id=assignee_account_id,
            assignee_name=assignee_name,
            project_key=_project_key,
            t_shirt_size=t_shirt_size,
            story_points=story_points,
            labels=labels,
            components=components,
            created_date=self._parse_datetime(fields.get("created")) or Issue.created_date,
            updated_date=self._parse_datetime(fields.get("updated")),
            resolution_date=self._parse_datetime(fields.get("resolutiondate")),
            started_date=self._parse_datetime(fields.get("statuscategorychangedate"))
        )
    
    def _parse_datetime(self, date_str: Optional[str]):
        """
        Parse datetime string from Jira API.
        
        Args:
            date_str: ISO format datetime string
            
        Returns:
            datetime object or None
        """
        if not date_str:
            return None
        
        try:
            from datetime import datetime
            # Jira returns ISO format: 2024-01-15T10:30:00.000+0000
            # Handle various formats
            if "." in date_str:
                # Remove milliseconds and timezone for simpler parsing
                date_str = date_str.split(".")[0]
            if "T" in date_str:
                return datetime.fromisoformat(date_str.replace("Z", ""))
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            logger.debug("datetime_parse_failed", date_str=date_str)
            return None
