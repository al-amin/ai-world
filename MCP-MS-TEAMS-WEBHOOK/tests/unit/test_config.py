"""
Unit tests for the MCP Teams Webhook configuration.

This module contains tests for the webhook configuration functionality.
"""

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from mcp_teams_webhook.models.base import WebhookConfig, WebhookStatus
from mcp_teams_webhook.teams.config import TeamsWebhookConfig


class TestTeamsWebhookConfig:
    """Tests for the TeamsWebhookConfig class."""

    def test_from_env_empty(self, monkeypatch):
        """Test creating config when no environment variables are set."""
        # Clear relevant environment variables
        for var in ["TEAMS_WEBHOOK_URL", "TEAMS_WEBHOOK_NAME", "TEAMS_WEBHOOK_CONFIG_FILE"]:
            monkeypatch.delenv(var, raising=False)
        
        config = TeamsWebhookConfig.from_env()
        
        assert config.default_webhook_name is None
        assert len(config.webhooks) == 0
    
    def test_from_env_with_url(self, monkeypatch):
        """Test creating config from environment variables with webhook URL."""
        # Set environment variables
        monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://webhook.office.com/webhookb2/123456789")
        monkeypatch.setenv("TEAMS_WEBHOOK_NAME", "test-webhook")
        monkeypatch.setenv("TEAMS_WEBHOOK_DESCRIPTION", "Test webhook from env")
        
        # Clear config file variable to ensure we're testing direct env vars
        monkeypatch.delenv("TEAMS_WEBHOOK_CONFIG_FILE", raising=False)
        
        config = TeamsWebhookConfig.from_env()
        
        assert config.default_webhook_name == "test-webhook"
        assert len(config.webhooks) == 1
        assert "test-webhook" in config.webhooks
        assert config.webhooks["test-webhook"].url == "https://webhook.office.com/webhookb2/123456789"
        assert config.webhooks["test-webhook"].description == "Test webhook from env"
    
    def test_from_file(self, tmp_path):
        """Test loading config from a file."""
        # Create a temporary config file
        config_data = {
            "webhooks": [
                {
                    "name": "webhook1",
                    "url": "https://webhook.office.com/webhookb2/123456789",
                    "description": "Test webhook 1",
                    "is_default": True,
                    "status": "active",
                    "created_at": "2023-01-01T00:00:00Z",
                },
                {
                    "name": "webhook2",
                    "url": "https://webhook.office.com/webhookb2/987654321",
                    "description": "Test webhook 2",
                    "is_default": False,
                    "status": "active",
                    "created_at": "2023-01-02T00:00:00Z",
                },
            ]
        }
        
        config_file = tmp_path / "webhook_config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        # Load config from file
        config = TeamsWebhookConfig.from_file(str(config_file))
        
        assert config.default_webhook_name == "webhook1"
        assert len(config.webhooks) == 2
        assert "webhook1" in config.webhooks
        assert "webhook2" in config.webhooks
        assert config.webhooks["webhook1"].is_default is True
        assert config.webhooks["webhook2"].is_default is False
    
    def test_from_file_invalid(self, tmp_path):
        """Test loading config from an invalid file."""
        # Create an invalid config file
        config_file = tmp_path / "invalid_config.json"
        with open(config_file, "w") as f:
            f.write("This is not valid JSON")
        
        # Load config from invalid file
        config = TeamsWebhookConfig.from_file(str(config_file))
        
        # Should return empty config with the file path set
        assert config.default_webhook_name is None
        assert len(config.webhooks) == 0
        assert config.config_file == str(config_file)
    
    def test_save_to_file(self, tmp_path):
        """Test saving config to a file."""
        config_file = tmp_path / "save_config.json"
        
        # Create a config with webhooks
        config = TeamsWebhookConfig(config_file=str(config_file))
        
        webhook1 = WebhookConfig(
            name="webhook1",
            url="https://webhook.office.com/webhookb2/123456789",
            description="Test webhook 1",
            is_default=True,
        )
        
        webhook2 = WebhookConfig(
            name="webhook2",
            url="https://webhook.office.com/webhookb2/987654321",
            description="Test webhook 2",
        )
        
        # Add webhooks
        config.add_webhook(webhook1, save=False)
        config.add_webhook(webhook2, save=False)
        
        # Save to file
        result = config.save_to_file()
        assert result is True
        
        # Verify file was created and contains expected content
        assert config_file.exists()
        
        # Load the saved file and verify content
        with open(config_file, "r") as f:
            saved_data = json.load(f)
            
        assert "webhooks" in saved_data
        assert len(saved_data["webhooks"]) == 2
        assert any(w["name"] == "webhook1" for w in saved_data["webhooks"])
        assert any(w["name"] == "webhook2" for w in saved_data["webhooks"])
    
    def test_get_webhook(self):
        """Test retrieving webhooks by name."""
        config = TeamsWebhookConfig()
        
        # Add webhooks
        webhook1 = WebhookConfig(
            name="webhook1",
            url="https://webhook.office.com/webhookb2/123456789",
            is_default=True,
        )
        
        webhook2 = WebhookConfig(
            name="webhook2",
            url="https://webhook.office.com/webhookb2/987654321",
        )
        
        config.add_webhook(webhook1, save=False)
        config.add_webhook(webhook2, save=False)
        
        # Test getting by name
        assert config.get_webhook("webhook1") == webhook1
        assert config.get_webhook("webhook2") == webhook2
        
        # Test getting default
        assert config.get_webhook() == webhook1
        
        # Test getting non-existent webhook
        assert config.get_webhook("non-existent") is None
    
    def test_add_webhook(self):
        """Test adding a webhook to the configuration."""
        config = TeamsWebhookConfig()
        
        # Add a webhook
        webhook = WebhookConfig(
            name="test-webhook",
            url="https://webhook.office.com/webhookb2/123456789",
            description="Test webhook",
        )
        
        result = config.add_webhook(webhook, save=False)
        assert result is True
        assert "test-webhook" in config.webhooks
        assert config.default_webhook_name == "test-webhook"  # First webhook becomes default
    
    def test_remove_webhook(self):
        """Test removing a webhook from the configuration."""
        config = TeamsWebhookConfig()
        
        # Add webhooks
        webhook1 = WebhookConfig(
            name="webhook1",
            url="https://webhook.office.com/webhookb2/123456789",
            is_default=True,
        )
        
        webhook2 = WebhookConfig(
            name="webhook2",
            url="https://webhook.office.com/webhookb2/987654321",
        )
        
        config.add_webhook(webhook1, save=False)
        config.add_webhook(webhook2, save=False)
        
        # Remove a webhook
        result = config.remove_webhook("webhook1", save=False)
        assert result is True
        assert "webhook1" not in config.webhooks
        assert "webhook2" in config.webhooks
        assert config.default_webhook_name == "webhook2"  # Default changed to remaining webhook
        
        # Remove non-existent webhook
        result = config.remove_webhook("non-existent", save=False)
        assert result is False
        
        # Remove last webhook
        result = config.remove_webhook("webhook2", save=False)
        assert result is True
        assert len(config.webhooks) == 0
        assert config.default_webhook_name is None