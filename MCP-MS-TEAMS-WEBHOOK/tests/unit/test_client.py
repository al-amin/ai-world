"""
Unit tests for the MCP Teams Webhook client.

This module contains tests for the Teams webhook client functionality.
"""

import asyncio
import json
from datetime import datetime
from unittest import mock

import httpx
import pytest

from mcp_teams_webhook.models.base import MessageStatus, WebhookConfig, WebhookStatus
from mcp_teams_webhook.models.messages import TextMessage
from mcp_teams_webhook.teams.client import TeamsWebhookClient
from mcp_teams_webhook.teams.config import TeamsWebhookConfig


class MockResponse:
    """Mock HTTP response for testing."""
    
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


@pytest.fixture
def mock_config():
    """Create a mock TeamsWebhookConfig for testing."""
    config = TeamsWebhookConfig()
    
    # Add a webhook
    webhook = WebhookConfig(
        name="test-webhook",
        url="https://webhook.office.com/webhookb2/123456789",
        description="Test webhook",
        is_default=True,
    )
    
    config.add_webhook(webhook, save=False)
    return config


@pytest.fixture
def client(mock_config):
    """Create a TeamsWebhookClient for testing."""
    return TeamsWebhookClient(config=mock_config)


class TestTeamsWebhookClient:
    """Tests for the TeamsWebhookClient class."""

    def test_init(self, mock_config):
        """Test client initialization."""
        client = TeamsWebhookClient(config=mock_config)
        
        assert client.config == mock_config
        assert client._message_history == []
        assert client._message_count_in_window == 0
        assert client._rate_limit_window == 1.0
    
    def test_create_text_message(self, client):
        """Test creating a text message."""
        message = client.create_text_message(
            text="Hello, world!",
            title="Test Message",
            webhook_name="test-webhook",
        )
        
        assert message.message_type == "text"
        assert message.text == "Hello, world!"
        assert message.title == "Test Message"
        assert message.webhook_name == "test-webhook"
    
    def test_create_adaptive_card(self, client):
        """Test creating an adaptive card."""
        card_elements = [
            {
                "type": "TextBlock",
                "text": "Hello, Adaptive Card!",
            }
        ]
        
        card = client.create_adaptive_card(
            card_elements=card_elements,
            title="Test Card",
            webhook_name="test-webhook",
        )
        
        assert card.message_type == "adaptive_card"
        assert card.card_elements == card_elements
        assert card.title == "Test Card"
        assert card.webhook_name == "test-webhook"
    
    def test_create_notification(self, client):
        """Test creating a notification message."""
        notification = client.create_notification(
            title="Alert",
            message="System maintenance scheduled",
            webhook_name="test-webhook",
        )
        
        assert notification.message_type == "notification"
        assert notification.title == "Alert"
        assert notification.message == "System maintenance scheduled"
        assert notification.webhook_name == "test-webhook"

    @pytest.mark.asyncio
    async def test_verify_webhook_success(self, client, monkeypatch):
        """Test successful webhook verification."""
        # Mock the HTTP post request to return a successful response
        async def mock_post(*args, **kwargs):
            return MockResponse(200, "1")
        
        # Apply the mock
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        
        # Verify the webhook
        result = await client.verify_webhook("test-webhook")
        
        assert result["valid"] is True
        assert result["status"] == "active"
        assert "working correctly" in result["message"]
    
    @pytest.mark.asyncio
    async def test_verify_webhook_failure(self, client, monkeypatch):
        """Test failed webhook verification."""
        # Mock the HTTP post request to return an error response
        async def mock_post(*args, **kwargs):
            return MockResponse(404, "Not Found")
        
        # Apply the mock
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        
        # Verify the webhook
        result = await client.verify_webhook("test-webhook")
        
        assert result["valid"] is False
        assert result["status"] == "error"
        assert "404" in result["message"]
    
    @pytest.mark.asyncio
    async def test_verify_webhook_exception(self, client, monkeypatch):
        """Test webhook verification with an exception."""
        # Mock the HTTP post request to raise an exception
        async def mock_post(*args, **kwargs):
            raise httpx.RequestError("Connection error")
        
        # Apply the mock
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        
        # Verify the webhook
        result = await client.verify_webhook("test-webhook")
        
        assert result["valid"] is False
        assert result["status"] == "error"
        assert "Connection error" in result["message"]
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, client, monkeypatch):
        """Test successful message sending."""
        # Create a message
        message = client.create_text_message(
            text="Hello, world!",
            webhook_name="test-webhook",
        )
        
        # Mock the HTTP post request to return a successful response
        async def mock_post(*args, **kwargs):
            return MockResponse(200, "1")
        
        # Apply the mock
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        
        # Send the message
        result = await client.send(message)
        
        assert result.status == MessageStatus.DELIVERED
        assert result.delivery_attempts == 1
        assert result.error_message is None
        
        # Verify message history
        assert len(client._message_history) == 1
        assert client._message_history[0] == result
    
    @pytest.mark.asyncio
    async def test_send_message_failure(self, client, monkeypatch):
        """Test failed message sending."""
        # Create a message
        message = client.create_text_message(
            text="Hello, world!",
            webhook_name="test-webhook",
        )
        
        # Mock the HTTP post request to return an error response
        async def mock_post(*args, **kwargs):
            return MockResponse(404, "Not Found")
        
        # Apply the mock
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        
        # Configure retry count to 0 for faster testing
        result = await client.send(message, retry_count=0)
        
        assert result.status == MessageStatus.FAILED
        assert result.delivery_attempts == 1
        assert "404" in result.error_message
        
        # Verify message history
        assert len(client._message_history) == 1
        assert client._message_history[0] == result
    
    @pytest.mark.asyncio
    async def test_send_message_retry(self, client, monkeypatch):
        """Test message sending with retry."""
        # Create a message
        message = client.create_text_message(
            text="Hello, world!",
            webhook_name="test-webhook",
        )
        
        # Counter to track number of attempts
        attempt_count = 0
        
        # Mock the HTTP post request to fail once then succeed
        async def mock_post(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count == 1:
                return MockResponse(429, "Too Many Requests")
            else:
                return MockResponse(200, "1")
        
        # Apply the mock
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        
        # Send the message
        result = await client.send(message, retry_count=1)
        
        assert result.status == MessageStatus.DELIVERED
        assert result.delivery_attempts == 2
        assert result.error_message is None
        assert attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_send_nonexistent_webhook(self, client):
        """Test sending a message with a non-existent webhook."""
        # Create a message with a non-existent webhook
        message = client.create_text_message(
            text="Hello, world!",
            webhook_name="non-existent",
        )
        
        # Send the message
        result = await client.send(message)
        
        assert result.status == MessageStatus.FAILED
        assert "not found" in result.error_message
    
    @pytest.mark.asyncio
    async def test_send_error_state_webhook(self, client):
        """Test sending a message with a webhook in error state."""
        # Set the webhook to error state
        webhook = client.config.get_webhook("test-webhook")
        webhook.status = WebhookStatus.ERROR
        webhook.error_message = "Previous error"
        
        # Create a message
        message = client.create_text_message(
            text="Hello, world!",
            webhook_name="test-webhook",
        )
        
        # Mock the verify_webhook method to return an error
        async def mock_verify(*args, **kwargs):
            return {
                "valid": False,
                "status": "error",
                "message": "Webhook is in error state",
            }
        
        # Apply the mock
        with mock.patch.object(client, "verify_webhook", mock_verify):
            # Send the message
            result = await client.send(message)
            
            assert result.status == MessageStatus.FAILED
            assert "error state" in result.error_message
    
    def test_get_message_history(self, client):
        """Test retrieving message history."""
        # Initially empty
        assert client.get_message_history() == []
        
        # Add some messages to history
        message1 = TextMessage(text="Message 1")
        message2 = TextMessage(text="Message 2")
        
        client._message_history = [message1, message2]
        
        # Get history
        history = client.get_message_history()
        
        assert len(history) == 2
        assert history[0] == message1
        assert history[1] == message2