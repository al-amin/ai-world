"""
Unit tests for the MCP Teams Webhook models.

This module contains tests for the base models, message models, and webhook
configuration models.
"""

import json
from datetime import datetime
from unittest import mock

import pytest
from pydantic import ValidationError

from mcp_teams_webhook.models.base import (
    MessageBase,
    MessageStatus,
    TeamsBaseModel,
    WebhookConfig,
    WebhookStatus,
)
from mcp_teams_webhook.models.constants import MAX_MESSAGE_SIZE_BYTES
from mcp_teams_webhook.models.messages import (
    AdaptiveCard,
    NotificationMessage,
    TextMessage,
)


class TestTeamsBaseModel:
    """Tests for the TeamsBaseModel class."""

    def test_from_dict(self):
        """Test creating a model from a dictionary."""
        data = {"name": "test", "value": 123}
        
        class TestModel(TeamsBaseModel):
            name: str
            value: int
        
        model = TestModel.from_dict(data)
        assert model.name == "test"
        assert model.value == 123
    
    def test_to_dict(self):
        """Test converting a model to a dictionary."""
        class TestModel(TeamsBaseModel):
            name: str
            value: int
            optional: str = None
        
        model = TestModel(name="test", value=123)
        data = model.to_dict()
        
        assert data == {"name": "test", "value": 123}
        assert "optional" not in data


class TestWebhookConfig:
    """Tests for the WebhookConfig class."""

    def test_valid_webhook_url(self):
        """Test that valid webhook URLs are accepted."""
        # Valid webhook URLs
        valid_urls = [
            "https://outlook.office.com/webhook/123456789",
            "https://webhook.office.com/webhookb2/123456789",
            "https://webhook.office365.com/webhookb2/123456789",
        ]
        
        for url in valid_urls:
            webhook = WebhookConfig(
                name="test",
                url=url,
                description="Test webhook",
            )
            assert webhook.url == url
    
    def test_invalid_webhook_url(self):
        """Test that invalid webhook URLs are rejected."""
        # Invalid webhook URLs
        invalid_urls = [
            "https://example.com/webhook",
            "http://webhook.office.com/webhook",  # Not HTTPS
            "ftp://webhook.office.com/webhook",   # Not HTTPS
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                WebhookConfig(
                    name="test",
                    url=url,
                    description="Test webhook",
                )


class TestMessageBase:
    """Tests for the MessageBase class."""

    def test_validate_size_within_limit(self):
        """Test that a message within size limits is valid."""
        message = TextMessage(
            message_type="text",
            text="Hello, world!",
        )
        
        assert message.validate_size() is True
    
    def test_validate_size_exceeds_limit(self):
        """Test that a message exceeding size limits is invalid."""
        # Create a message that exceeds the size limit
        large_text = "X" * (MAX_MESSAGE_SIZE_BYTES + 1000)
        
        message = TextMessage(
            message_type="text",
            text=large_text,
        )
        
        assert message.validate_size() is False


class TestTextMessage:
    """Tests for the TextMessage class."""

    def test_to_teams_payload_simple(self):
        """Test converting a simple text message to Teams payload."""
        message = TextMessage(
            text="Hello, world!",
        )
        
        payload = message.to_teams_payload()
        
        assert payload["type"] == "message"
        assert payload["text"] == "Hello, world!"
        
    def test_to_teams_payload_with_title(self):
        """Test converting a text message with title to Teams payload."""
        message = TextMessage(
            text="Hello, world!",
            title="Test Message",
            use_markdown=True,
        )
        
        payload = message.to_teams_payload()
        
        assert payload["type"] == "message"
        assert "## Test Message" in payload["text"]
        assert "Hello, world!" in payload["text"]


class TestAdaptiveCard:
    """Tests for the AdaptiveCard class."""

    def test_to_teams_payload(self):
        """Test converting an adaptive card to Teams payload."""
        card_elements = [
            {
                "type": "TextBlock",
                "text": "Hello, Adaptive Card!",
                "weight": "bolder",
                "size": "large",
            },
            {
                "type": "TextBlock",
                "text": "This is a simple adaptive card example.",
                "wrap": True,
            },
        ]
        
        card = AdaptiveCard(
            title="Test Card",
            card_elements=card_elements,
            fallback_text="Your client doesn't support Adaptive Cards.",
        )
        
        payload = card.to_teams_payload()
        
        assert payload["type"] == "message"
        assert payload["attachments"][0]["contentType"] == "application/vnd.microsoft.card.adaptive"
        assert payload["attachments"][0]["content"]["type"] == "AdaptiveCard"
        assert payload["attachments"][0]["content"]["body"] == card_elements
        assert payload["summary"] == "Test Card"
        assert payload["text"] == "Your client doesn't support Adaptive Cards."


class TestNotificationMessage:
    """Tests for the NotificationMessage class."""

    def test_to_teams_payload(self):
        """Test converting a notification message to Teams payload."""
        notification = NotificationMessage(
            title="Alert",
            message="System maintenance scheduled",
            priority="important",
            image_url="https://example.com/image.png",
            facts=[
                {"name": "Start Time", "value": "10:00 AM"},
                {"name": "Duration", "value": "2 hours"},
            ],
            color="FF0000",
        )
        
        payload = notification.to_teams_payload()
        
        assert payload["type"] == "message"
        assert payload["attachments"][0]["contentType"] == "application/vnd.microsoft.teams.card.o365connector"
        assert payload["attachments"][0]["content"]["summary"] == "Alert"
        assert payload["attachments"][0]["content"]["themeColor"] == "FF0000"
        
        section = payload["attachments"][0]["content"]["sections"][0]
        assert section["activityTitle"] == "Alert"
        assert section["activitySubtitle"] == "System maintenance scheduled"
        assert section["facts"] == notification.facts
        assert section["activityImage"] == str(notification.image_url)