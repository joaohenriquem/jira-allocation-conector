"""
Unit tests for ConfigLoader.

Tests cover:
- Loading valid configuration from YAML
- Validation of invalid configurations (missing fields, wrong types)
- Getting Jira credentials with different auth types
- Error handling for missing config file
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.config.config_loader import ConfigLoader
from src.models.data_models import JiraConfig


class TestConfigLoaderLoad:
    """Tests for ConfigLoader.load() method."""

    def test_load_valid_config(self, tmp_path):
        """Test loading a valid configuration file."""
        config_content = {
            "cache": {"ttl_seconds": 600},
            "projects": {
                "keys": ["PROJ1", "PROJ2"],
                "default_capacity_hours": 35.0,
            },
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_content))

        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://test.atlassian.net",
            "JIRA_USERNAME": "user@test.com",
            "JIRA_API_TOKEN": "test-token",
        }):
            loader = ConfigLoader(str(config_file))
            app_config = loader.load()

        assert app_config.cache_ttl_seconds == 600
        assert app_config.projects == ["PROJ1", "PROJ2"]
        assert app_config.default_capacity_hours == 35.0
        assert app_config.jira.base_url == "https://test.atlassian.net"

    def test_load_config_with_defaults(self, tmp_path):
        """Test loading config uses defaults for missing optional fields."""
        config_content = {}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_content))

        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://test.atlassian.net",
            "JIRA_USERNAME": "user@test.com",
            "JIRA_API_TOKEN": "test-token",
        }):
            loader = ConfigLoader(str(config_file))
            app_config = loader.load()

        assert app_config.cache_ttl_seconds == 900  # default
        assert app_config.projects == []  # default
        assert app_config.default_capacity_hours == 40.0  # default

    def test_load_missing_config_file_raises_error(self):
        """Test that loading a non-existent config file raises FileNotFoundError."""
        loader = ConfigLoader("nonexistent_config.yaml")

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load()

        assert "Configuration file not found" in str(exc_info.value)


class TestConfigLoaderValidate:
    """Tests for ConfigLoader.validate() method."""

    def test_validate_valid_config(self):
        """Test validation passes for valid configuration."""
        config = {
            "cache": {"ttl_seconds": 600},
            "projects": {
                "keys": ["PROJ1"],
                "default_capacity_hours": 40.0,
            },
        }
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert errors == []

    def test_validate_invalid_ttl_type(self):
        """Test validation fails when ttl_seconds is not a number."""
        config = {"cache": {"ttl_seconds": "invalid"}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("ttl_seconds must be a number" in e for e in errors)

    def test_validate_negative_ttl(self):
        """Test validation fails when ttl_seconds is negative."""
        config = {"cache": {"ttl_seconds": -100}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("ttl_seconds must be positive" in e for e in errors)

    def test_validate_zero_ttl(self):
        """Test validation fails when ttl_seconds is zero."""
        config = {"cache": {"ttl_seconds": 0}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("ttl_seconds must be positive" in e for e in errors)

    def test_validate_invalid_project_keys_type(self):
        """Test validation fails when projects.keys is not a list."""
        config = {"projects": {"keys": "not-a-list"}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("projects.keys must be a list" in e for e in errors)

    def test_validate_invalid_capacity_type(self):
        """Test validation fails when default_capacity_hours is not a number."""
        config = {"projects": {"default_capacity_hours": "invalid"}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("default_capacity_hours must be a number" in e for e in errors)

    def test_validate_negative_capacity(self):
        """Test validation fails when default_capacity_hours is negative."""
        config = {"projects": {"default_capacity_hours": -10}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("default_capacity_hours must be positive" in e for e in errors)

    def test_validate_invalid_overload_threshold_type(self):
        """Test validation fails when overload_threshold is not a number."""
        config = {"allocation": {"overload_threshold": "high"}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("overload_threshold must be a number" in e for e in errors)

    def test_validate_negative_overload_threshold(self):
        """Test validation fails when overload_threshold is negative."""
        config = {"allocation": {"overload_threshold": -50}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("overload_threshold must be positive" in e for e in errors)

    def test_validate_invalid_underutilization_threshold_type(self):
        """Test validation fails when underutilization_threshold is not a number."""
        config = {"allocation": {"underutilization_threshold": "low"}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("underutilization_threshold must be a number" in e for e in errors)

    def test_validate_negative_underutilization_threshold(self):
        """Test validation fails when underutilization_threshold is negative."""
        config = {"allocation": {"underutilization_threshold": -10}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("underutilization_threshold must be non-negative" in e for e in errors)

    def test_validate_invalid_ai_enabled_type(self):
        """Test validation fails when ai_assistant.enabled is not a boolean."""
        config = {"ai_assistant": {"enabled": "yes"}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("ai_assistant.enabled must be a boolean" in e for e in errors)

    def test_validate_invalid_ai_provider(self):
        """Test validation fails when ai_assistant.provider is invalid."""
        config = {"ai_assistant": {"provider": "invalid_provider"}}
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert any("provider must be 'openai' or 'anthropic'" in e for e in errors)

    def test_validate_non_dict_config(self):
        """Test validation fails when config is not a dictionary."""
        loader = ConfigLoader()
        errors = loader.validate("not a dict")
        assert any("Configuration must be a dictionary" in e for e in errors)

    def test_validate_multiple_errors(self):
        """Test validation returns all errors when multiple issues exist."""
        config = {
            "cache": {"ttl_seconds": "invalid"},
            "projects": {"keys": "not-a-list", "default_capacity_hours": -10},
        }
        loader = ConfigLoader()
        errors = loader.validate(config)
        assert len(errors) >= 3


class TestConfigLoaderGetJiraCredentials:
    """Tests for ConfigLoader.get_jira_credentials() method."""

    def test_get_jira_credentials_api_token(self):
        """Test getting credentials with API Token authentication."""
        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://test.atlassian.net",
            "JIRA_USERNAME": "user@test.com",
            "JIRA_API_TOKEN": "api-token-123",
        }, clear=True):
            config = ConfigLoader.get_jira_credentials()

        assert config.base_url == "https://test.atlassian.net"
        assert config.auth_type == "api_token"
        assert config.username == "user@test.com"
        assert config.api_token == "api-token-123"
        assert config.personal_access_token is None

    def test_get_jira_credentials_pat(self):
        """Test getting credentials with Personal Access Token authentication."""
        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://jira.company.com",
            "JIRA_PERSONAL_ACCESS_TOKEN": "pat-token-456",
        }, clear=True):
            config = ConfigLoader.get_jira_credentials()

        assert config.base_url == "https://jira.company.com"
        assert config.auth_type == "pat"
        assert config.personal_access_token == "pat-token-456"
        assert config.username is None
        assert config.api_token is None

    def test_get_jira_credentials_pat_takes_precedence(self):
        """Test that PAT takes precedence when both auth types are provided."""
        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://jira.company.com",
            "JIRA_USERNAME": "user@test.com",
            "JIRA_API_TOKEN": "api-token-123",
            "JIRA_PERSONAL_ACCESS_TOKEN": "pat-token-456",
        }, clear=True):
            config = ConfigLoader.get_jira_credentials()

        assert config.auth_type == "pat"
        assert config.personal_access_token == "pat-token-456"

    def test_get_jira_credentials_strips_trailing_slash(self):
        """Test that trailing slash is removed from base URL."""
        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://test.atlassian.net/",
            "JIRA_PERSONAL_ACCESS_TOKEN": "pat-token",
        }, clear=True):
            config = ConfigLoader.get_jira_credentials()

        assert config.base_url == "https://test.atlassian.net"

    def test_get_jira_credentials_missing_base_url(self):
        """Test error when JIRA_BASE_URL is missing."""
        with patch.dict(os.environ, {
            "JIRA_USERNAME": "user@test.com",
            "JIRA_API_TOKEN": "api-token",
        }, clear=True):
            # Remove JIRA_BASE_URL if it exists
            os.environ.pop("JIRA_BASE_URL", None)
            
            with pytest.raises(ValueError) as exc_info:
                ConfigLoader.get_jira_credentials()

        assert "JIRA_BASE_URL environment variable is required" in str(exc_info.value)

    def test_get_jira_credentials_missing_all_auth(self):
        """Test error when no authentication credentials are provided."""
        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://test.atlassian.net",
        }, clear=True):
            # Remove auth-related env vars
            os.environ.pop("JIRA_USERNAME", None)
            os.environ.pop("JIRA_API_TOKEN", None)
            os.environ.pop("JIRA_PERSONAL_ACCESS_TOKEN", None)
            
            with pytest.raises(ValueError) as exc_info:
                ConfigLoader.get_jira_credentials()

        assert "Jira credentials not configured" in str(exc_info.value)

    def test_get_jira_credentials_api_token_missing_username(self):
        """Test error when API token is provided but username is missing."""
        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://test.atlassian.net",
            "JIRA_API_TOKEN": "api-token",
        }, clear=True):
            os.environ.pop("JIRA_USERNAME", None)
            os.environ.pop("JIRA_PERSONAL_ACCESS_TOKEN", None)
            
            with pytest.raises(ValueError) as exc_info:
                ConfigLoader.get_jira_credentials()

        assert "Jira credentials not configured" in str(exc_info.value)


class TestConfigLoaderIntegration:
    """Integration tests for ConfigLoader."""

    def test_load_raises_on_invalid_config(self, tmp_path):
        """Test that load() raises ValueError when config validation fails."""
        config_content = {
            "cache": {"ttl_seconds": "invalid"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_content))

        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://test.atlassian.net",
            "JIRA_PERSONAL_ACCESS_TOKEN": "pat-token",
        }):
            loader = ConfigLoader(str(config_file))
            
            with pytest.raises(ValueError) as exc_info:
                loader.load()

        assert "Configuration validation failed" in str(exc_info.value)

    def test_load_empty_yaml_file(self, tmp_path):
        """Test loading an empty YAML file uses all defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://test.atlassian.net",
            "JIRA_PERSONAL_ACCESS_TOKEN": "pat-token",
        }):
            loader = ConfigLoader(str(config_file))
            app_config = loader.load()

        assert app_config.cache_ttl_seconds == 900
        assert app_config.projects == []
        assert app_config.default_capacity_hours == 40.0
