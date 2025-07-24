"""
Base models for the MCP MS Teams Webhook server.

This module provides base models and common utilities for the MS Teams webhook
integration, including message base classes and configuration models.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TypeVar

from pydantic import BaseModel, Field, HttpUrl, validator

from .constants import (
    EMPTY_DICT,
    EMPTY_LIST,
    EMPTY_STRING,
    MAX_MESSAGE_SIZE_BYTES,
    MESSAGE_STATUS_PENDING,
    MESSAGE_TYPE_TEXT,
    PRIORITY_NORMAL,
    WEBHOOK_STATUS_ACTIVE,
)

# Type variable for the return type of from_dict
T = TypeVar("T", bound="TeamsBaseModel")


class MessageType(str, Enum):
    """Enumeration of supported MS Teams message types."""

    TEXT = MESSAGE_TYPE_TEXT
    ADAPTIVE_CARD = "adaptive_card"
    NOTIFICATION = "notification"


class MessagePriority(str, Enum):
    """Enumeration of message priority levels."""

    NORMAL = PRIORITY_NORMAL
    IMPORTANT = "important"
    URGENT = "urgent"


class MessageStatus(str, Enum):
    """Enumeration of message delivery statuses."""

    PENDING = MESSAGE_STATUS_PENDING
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookStatus(str, Enum):
    """Enumeration of webhook statuses."""

    ACTIVE = WEBHOOK_STATUS_ACTIVE
    INACTIVE = "inactive"
    ERROR = "error"


class TeamsBaseModel(BaseModel):
    """
    Base model for all MS Teams related models.

    Provides common methods and utilities for working with MS Teams data.
    """

    @classmethod
    def from_dict(cls: type[T], data: Dict[str, Any]) -> T:
        """
        Create a model instance from a dictionary.

        Args:
            data: Dictionary containing model data

        Returns:
            An instance of the model
        """
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary representation.

        Returns:
            A dictionary representation of the model
        """
        return self.model_dump(exclude_none=True)


class WebhookConfig(TeamsBaseModel):
    """
    Configuration for an MS Teams webhook.

    Contains the webhook URL and associated metadata.
    """

    name: str = Field(..., description="Unique name for this webhook configuration")
    url: HttpUrl = Field(..., description="MS Teams incoming webhook URL")
    description: Optional[str] = Field(
        default=None, description="Description of this webhook's purpose"
    )
    status: WebhookStatus = Field(
        default=WebhookStatus.ACTIVE, description="Current status of this webhook"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="When this configuration was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="When this configuration was last updated"
    )
    is_default: bool = Field(
        default=False, description="Whether this is the default webhook"
    )
    error_message: Optional[str] = Field(
        default=None, description="Last error message if status is ERROR"
    )

    @validator("url")
    def validate_webhook_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate that the webhook URL is properly formatted for MS Teams."""
        url_str = str(v)
        if not (
            "webhook.office.com" in url_str
            or "webhook.office365.com" in url_str
            or "outlook.office.com" in url_str
        ):
            raise ValueError("URL does not appear to be a valid MS Teams webhook URL")
        return v


class MessageBase(TeamsBaseModel):
    """
    Base class for all MS Teams messages.

    Provides common properties and methods for all message types.
    """

    message_type: MessageType = Field(
        ..., description="Type of message (text, adaptive_card, notification)"
    )
    webhook_name: Optional[str] = Field(
        default=None,
        description="Name of the webhook configuration to use. If None, the default webhook will be used.",
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL, description="Message priority"
    )
    status: MessageStatus = Field(
        default=MessageStatus.PENDING, description="Current delivery status"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When this message was created"
    )
    delivery_attempts: int = Field(
        default=0, description="Number of delivery attempts made"
    )
    last_attempt: Optional[datetime] = Field(
        default=None, description="When the last delivery attempt was made"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if delivery failed"
    )

    def validate_size(self) -> bool:
        """
        Check if the message size is within MS Teams limits.

        Returns:
            True if message is within size limits, False otherwise
        """
        message_json = self.model_dump_json()
        return len(message_json.encode("utf-8")) <= MAX_MESSAGE_SIZE_BYTES