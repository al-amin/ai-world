"""
Shared pytest fixtures for MCP Teams Webhook tests.

This module provides fixtures that can be used across all test modules.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import httpx
import pytest
from pydantic import HttpUrl

from mcp_teams_webhook.models.base import WebhookConfig, WebhookStatus
from mcp_teams_webhook.teams.client import TeamsWebhookClient
from mcp_teams_webhook.teams.config import TeamsWebhookConfig


class MockAsyncResponse:
    """Mock httpx.Response for async tests."""
    
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text
        
    def __await__(self):
        """Make awaitable for async tests."""
        async def _await_impl():
            return self
        return _await_impl().__await__()


@pytest.fixture
def sample_webhook_config() -> Dict:
    """Sample webhook configuration data."""
    return {
        "webhooks": [
            {
                "name": "test-webhook",
                "url": "https://webhook.office.com/webhookb2/123456789/IncomingWebhook/abcdef/123456",
                "description": "Test webhook for unit tests",
                "is_default": True,
                "status": "active",
                "created_at": datetime.now().isoformat(),
            }
        ]
    }


@pytest.fixture
def config_file(tmp_path, sample_webhook_config) -> Path:
    """Create a temporary webhook configuration file."""
    config_file = tmp_path / "test_webhook_config.json"
    
    with open(config_file, "w") as f:
        json.dump(sample_webhook_config, f)
        
    return config_file


@pytest.fixture
def webhook_config(config_file) -> TeamsWebhookConfig:
    """Create a TeamsWebhookConfig instance from the fixture file."""
    return TeamsWebhookConfig.from_file(str(config_file))


@pytest.fixture
def webhook_client(webhook_config) -> TeamsWebhookClient:
    """Create a TeamsWebhookClient instance with the fixture configuration."""
    return TeamsWebhookClient(config=webhook_config)


@pytest.fixture
def mock_httpx_post(monkeypatch):
    """Mock httpx.AsyncClient.post method."""
    
    async def mock_post(*args, **kwargs):
        """Mock post that returns a success response."""
        return MockAsyncResponse(200, "1")
    
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    return mock_post