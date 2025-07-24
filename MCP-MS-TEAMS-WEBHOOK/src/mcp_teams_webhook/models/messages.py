"""
Models for MS Teams messages.

This module provides Pydantic models for different types of MS Teams messages,
including text messages, adaptive cards, and notifications.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import Field, HttpUrl, validator

from .base import MessageBase, MessagePriority, MessageType
from .constants import EMPTY_DICT, EMPTY_LIST, EMPTY_STRING


class TextMessage(MessageBase):
    """
    A simple text message to be sent to MS Teams.

    This message type supports plain text and markdown formatting.
    """

    message_type: MessageType = MessageType.TEXT
    text: str = Field(..., description="The message text content")
    title: Optional[str] = Field(default=None, description="Optional message title")
    subtitle: Optional[str] = Field(default=None, description="Optional message subtitle")
    use_markdown: bool = Field(
        default=True, description="Whether to render text as markdown"
    )

    def to_teams_payload(self) -> Dict[str, Any]:
        """
        Convert the message to the format expected by MS Teams webhooks.

        Returns:
            A dictionary containing the formatted message
        """
        # For simple text messages, just use the text field without type specification
        if self.title and self.use_markdown:
            text = f"## {self.title}\n\n{self.text}"
        elif self.subtitle and self.use_markdown:
            title_part = f"## {self.title}\n\n" if self.title else ""
            text = f"{title_part}### {self.subtitle}\n\n{self.text}"
        else:
            text = self.text
            
        # Simple format that's most compatible with Teams webhooks
        return {
            "text": text
        }


class AdaptiveCardAction(MessageBase):
    """An action element for an Adaptive Card."""

    type: str = Field(..., description="Type of action (Action.OpenUrl, Action.Submit, etc.)")
    title: str = Field(..., description="Button or action title")
    url: Optional[HttpUrl] = Field(
        default=None, description="URL for Action.OpenUrl actions"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Data for Action.Submit actions"
    )

    @validator("type")
    def validate_action_type(cls, v: str) -> str:
        """Validate that the action type is supported by MS Teams."""
        valid_types = [
            "Action.OpenUrl",
            "Action.Submit",
            "Action.ShowCard",
            "Action.ToggleVisibility",
        ]
        if v not in valid_types:
            raise ValueError(
                f"Action type '{v}' is not supported. Must be one of: {', '.join(valid_types)}"
            )
        return v


class AdaptiveCardElement(MessageBase):
    """A content element for an Adaptive Card."""

    type: str = Field(..., description="Type of element (TextBlock, Image, etc.)")
    id: Optional[str] = Field(default=None, description="Optional element ID")
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Element properties"
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the element to a dictionary for inclusion in an Adaptive Card.

        Returns:
            A dictionary representation of the element
        """
        result = {"type": self.type}
        if self.id:
            result["id"] = self.id
        result.update(self.properties)
        return result


class AdaptiveCard(MessageBase):
    """
    An Adaptive Card message to be sent to MS Teams.

    This message type supports complex card layouts with interactive elements.
    """

    message_type: MessageType = MessageType.ADAPTIVE_CARD
    title: Optional[str] = Field(
        default=None, description="Card title (appears outside the card)"
    )
    card_elements: List[Dict[str, Any]] = Field(
        ..., description="Elements of the adaptive card"
    )
    card_actions: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Actions for the adaptive card"
    )
    version: str = Field(default="1.5", description="Adaptive Card schema version")
    fallback_text: Optional[str] = Field(
        default=None,
        description="Text to display if the client doesn't support Adaptive Cards",
    )

    def to_teams_payload(self) -> Dict[str, Any]:
        """
        Convert the message to the format expected by MS Teams webhooks.

        Returns:
            A dictionary containing the formatted message with Adaptive Card
        """
        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": self.version,
            "body": self.card_elements
        }

        if self.card_actions:
            card["actions"] = self.card_actions

        # Format specifically for Teams incoming webhooks
        payload = {
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card
                }
            ]
        }

        # Add fallback text if provided
        if self.fallback_text:
            payload["text"] = self.fallback_text
        elif self.title:
            # Use title as fallback if no specific fallback text is provided
            payload["text"] = self.title

        return payload


class NotificationMessage(MessageBase):
    """
    A notification message to be sent to MS Teams.

    This message type is designed for alerts and important notifications.
    """

    message_type: MessageType = MessageType.NOTIFICATION
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    priority: MessagePriority = MessagePriority.IMPORTANT
    image_url: Optional[HttpUrl] = Field(
        default=None, description="Optional image to display with notification"
    )
    actions: List[Dict[str, Any]] = Field(
        default_factory=list, description="Action buttons for the notification"
    )
    facts: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Key-value pairs to display in the notification"
    )
    color: Optional[str] = Field(
        default=None, description="Color accent for the notification (hex code)"
    )

    def to_teams_payload(self) -> Dict[str, Any]:
        """
        Convert the message to the format expected by MS Teams webhooks.

        Returns:
            A dictionary containing the formatted message with notification card
        """
        # Create Office 365 Connector Card (legacy format supported by webhooks)
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": self.title,
            "themeColor": self.color or "0078D7"
        }
        
        # Add sections with activity details
        sections = [{"activityTitle": self.title, "activitySubtitle": self.message}]
        
        if self.facts:
            sections[0]["facts"] = self.facts
            
        if self.image_url:
            sections[0]["activityImage"] = str(self.image_url)
            
        card["sections"] = sections
        
        # Add potential actions if any
        if self.actions:
            card["potentialAction"] = self.actions

        # Format specifically for Teams incoming webhooks
        return card