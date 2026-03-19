"""
Configuration loader for Jira Allocation Connector.

This module handles loading and validating configuration from YAML files
and environment variables.
"""

import os
from pathlib import Path
from typing import List, Optional

import yaml
from dotenv import load_dotenv

from src.models.data_models import AIConfig, AppConfig, JiraConfig


class ConfigLoader:
    """Loads and validates application configuration from YAML and environment variables."""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize loader with configuration file path.

        Args:
            config_path: Path to the YAML configuration file.
        """
        self.config_path = Path(config_path)
        # Load environment variables from .env file if it exists
        load_dotenv()

    def load(self) -> AppConfig:
        """
        Load and validate configuration from YAML and environment variables.

        Returns:
            AppConfig: Validated application configuration.

        Raises:
            FileNotFoundError: If the configuration file doesn't exist.
            ValueError: If the configuration is invalid.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f) or {}

        errors = self.validate(config_dict)
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

        jira_config = self.get_jira_credentials()
        ai_config = self._get_ai_config(config_dict)

        # Extract configuration values with defaults
        cache_config = config_dict.get("cache", {})
        projects_config = config_dict.get("projects", {})

        return AppConfig(
            jira=jira_config,
            cache_ttl_seconds=cache_config.get("ttl_seconds", 900),
            projects=projects_config.get("keys", []),
            default_capacity_hours=projects_config.get("default_capacity_hours", 40.0),
        )

    def validate(self, config: dict) -> List[str]:
        """
        Validate configuration and return list of errors.

        Args:
            config: Configuration dictionary to validate.

        Returns:
            List of error messages (empty if valid).
        """
        errors: List[str] = []

        if not isinstance(config, dict):
            errors.append("Configuration must be a dictionary")
            return errors

        # Validate cache section
        cache_config = config.get("cache", {})
        if cache_config:
            ttl = cache_config.get("ttl_seconds")
            if ttl is not None:
                if not isinstance(ttl, (int, float)):
                    errors.append("cache.ttl_seconds must be a number")
                elif ttl <= 0:
                    errors.append("cache.ttl_seconds must be positive")

        # Validate projects section
        projects_config = config.get("projects", {})
        if projects_config:
            keys = projects_config.get("keys")
            if keys is not None and not isinstance(keys, list):
                errors.append("projects.keys must be a list")

            capacity = projects_config.get("default_capacity_hours")
            if capacity is not None:
                if not isinstance(capacity, (int, float)):
                    errors.append("projects.default_capacity_hours must be a number")
                elif capacity <= 0:
                    errors.append("projects.default_capacity_hours must be positive")

        # Validate allocation section
        allocation_config = config.get("allocation", {})
        if allocation_config:
            overload = allocation_config.get("overload_threshold")
            if overload is not None:
                if not isinstance(overload, (int, float)):
                    errors.append("allocation.overload_threshold must be a number")
                elif overload <= 0:
                    errors.append("allocation.overload_threshold must be positive")

            underutil = allocation_config.get("underutilization_threshold")
            if underutil is not None:
                if not isinstance(underutil, (int, float)):
                    errors.append("allocation.underutilization_threshold must be a number")
                elif underutil < 0:
                    errors.append("allocation.underutilization_threshold must be non-negative")

        # Validate ai_assistant section
        ai_config = config.get("ai_assistant", {})
        if ai_config:
            enabled = ai_config.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                errors.append("ai_assistant.enabled must be a boolean")

            provider = ai_config.get("provider")
            if provider is not None and provider not in ("openai", "anthropic"):
                errors.append("ai_assistant.provider must be 'openai' or 'anthropic'")

        return errors

    @staticmethod
    def get_jira_credentials() -> JiraConfig:
        """
        Get Jira credentials from environment variables.

        Reads the following environment variables:
        - JIRA_BASE_URL: Base URL of the Jira instance
        - JIRA_USERNAME: Username for API token authentication
        - JIRA_API_TOKEN: API token for Jira Cloud
        - JIRA_PERSONAL_ACCESS_TOKEN: PAT for Jira Server/Data Center

        Returns:
            JiraConfig: Configuration with credentials from environment.

        Raises:
            ValueError: If required credentials are missing or invalid.
        """
        base_url = os.getenv("JIRA_BASE_URL", "")
        username = os.getenv("JIRA_USERNAME")
        api_token = os.getenv("JIRA_API_TOKEN")
        pat = os.getenv("JIRA_PERSONAL_ACCESS_TOKEN")

        if not base_url:
            raise ValueError("JIRA_BASE_URL environment variable is required")

        # Determine auth type based on provided credentials
        if pat:
            # Personal Access Token takes precedence (Server/Data Center)
            return JiraConfig(
                base_url=base_url.rstrip("/"),
                auth_type="pat",
                personal_access_token=pat,
            )
        elif api_token and username:
            # API Token authentication (Cloud)
            return JiraConfig(
                base_url=base_url.rstrip("/"),
                auth_type="api_token",
                username=username,
                api_token=api_token,
            )
        else:
            raise ValueError(
                "Jira credentials not configured. Provide either "
                "JIRA_PERSONAL_ACCESS_TOKEN (for Server/Data Center) or "
                "JIRA_USERNAME and JIRA_API_TOKEN (for Cloud)"
            )

    @staticmethod
    def _get_ai_config(config: dict) -> Optional[AIConfig]:
        """
        Get AI assistant configuration from YAML and environment variables.

        Args:
            config: Configuration dictionary.

        Returns:
            AIConfig if AI is enabled, None otherwise.
        """
        ai_config = config.get("ai_assistant", {})
        enabled = ai_config.get("enabled", False)

        if not enabled:
            return AIConfig(enabled=False)

        # Get API key from environment based on provider
        provider = ai_config.get("provider", "openai")
        api_key: Optional[str] = None

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")

        return AIConfig(
            enabled=enabled,
            api_key=api_key,
            model=ai_config.get("model", "gpt-4"),
            provider=provider,
        )
