"""
Message handling mixins and classes for MS Teams webhook integration.

This module provides mixins for different types of MS Teams messages,
allowing for a modular approach to message creation and delivery.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import httpx

from ..models.base import MessageBase, MessageStatus, WebhookConfig
from ..models.constants import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY,
    MAX_REQUESTS_PER_SECOND,
    MESSAGE_STATUS_DELIVERED,
    MESSAGE_STATUS_FAILED,
    MESSAGE_STATUS_RETRYING,
)
from ..models.messages import AdaptiveCard, NotificationMessage, TextMessage

# Configure logging
logger = logging.getLogger("mcp-teams-webhook")


class MessageMixin:
    """Base mixin for all message types with common functionality."""

    def _update_message_status(
        self, message: MessageBase, status: MessageStatus, error: Optional[str] = None
    ) -> MessageBase:
        """
        Update the status and related fields of a message.

        Args:
            message: The message to update
            status: The new status
            error: Optional error message

        Returns:
            The updated message
        """
        message.status = status
        message.last_attempt = datetime.now()
        message.delivery_attempts += 1
        
        if error:
            message.error_message = error
            
        return message


class TextMessageMixin(MessageMixin):
    """Mixin for handling text messages."""

    def create_text_message(
        self,
        text: str,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        use_markdown: bool = True,
        webhook_name: Optional[str] = None,
    ) -> TextMessage:
        """
        Create a new text message.

        Args:
            text: Main message content
            title: Optional message title
            subtitle: Optional message subtitle
            use_markdown: Whether to render text as markdown
            webhook_name: Name of the webhook to use

        Returns:
            A new TextMessage instance
        """
        return TextMessage(
            text=text,
            title=title,
            subtitle=subtitle,
            use_markdown=use_markdown,
            webhook_name=webhook_name,
        )


class AdaptiveCardMixin(MessageMixin):
    """Mixin for handling adaptive card messages."""

    def create_adaptive_card(
        self,
        card_elements: List[Dict[str, Any]],
        title: Optional[str] = None,
        card_actions: Optional[List[Dict[str, Any]]] = None,
        fallback_text: Optional[str] = None,
        webhook_name: Optional[str] = None,
    ) -> AdaptiveCard:
        """
        Create a new adaptive card message.

        Args:
            card_elements: The main elements of the card
            title: Optional card title
            card_actions: Optional card actions
            fallback_text: Text to display if client doesn't support cards
            webhook_name: Name of the webhook to use

        Returns:
            A new AdaptiveCard instance
        """
        return AdaptiveCard(
            card_elements=card_elements,
            title=title,
            card_actions=card_actions,
            fallback_text=fallback_text,
            webhook_name=webhook_name,
        )


class NotificationMixin(MessageMixin):
    """Mixin for handling notification messages."""

    def create_notification(
        self,
        title: str,
        message: str,
        image_url: Optional[str] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
        facts: Optional[List[Dict[str, str]]] = None,
        color: Optional[str] = None,
        webhook_name: Optional[str] = None,
    ) -> NotificationMessage:
        """
        Create a new notification message.

        Args:
            title: Notification title
            message: Main notification content
            image_url: Optional image to include
            actions: Optional action buttons
            facts: Optional key-value pairs to display
            color: Optional color accent for the notification
            webhook_name: Name of the webhook to use

        Returns:
            A new NotificationMessage instance
        """
        return NotificationMessage(
            title=title,
            message=message,
            image_url=image_url,
            actions=actions or [],
            facts=facts,
            color=color,
            webhook_name=webhook_name,
        )


class MessageDeliveryMixin:
    """Mixin for handling message delivery to MS Teams webhooks."""

    def _get_rate_limit_delay(
        self, requests_made: int, time_window: float = 1.0
    ) -> float:
        """
        Calculate delay needed to respect rate limits.

        Args:
            requests_made: Number of requests already made in the time window
            time_window: Time window in seconds

        Returns:
            Delay in seconds to maintain rate limit
        """
        if requests_made >= MAX_REQUESTS_PER_SECOND:
            # Calculate time to wait until next request can be made
            return time_window
        return 0
        
    async def send_message(
        self,
        message: MessageBase,
        webhook_config: WebhookConfig,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        retry_count: int = DEFAULT_RETRY_COUNT,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> MessageBase:
        """
        Send a message to an MS Teams webhook.

        Args:
            message: The message to send
            webhook_config: The webhook configuration to use
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            retry_delay: Delay between retries in seconds

        Returns:
            The message with updated status
        """
        if not hasattr(message, "to_teams_payload"):
            error_msg = f"Message of type {message.__class__.__name__} does not have to_teams_payload method"
            logger.error(error_msg)
            return self._update_message_status(
                message, MessageStatus.FAILED, error_msg
            )
            
        # Check message size
        if not message.validate_size():
            error_msg = "Message exceeds maximum size allowed by MS Teams (28KB)"
            logger.error(error_msg)
            return self._update_message_status(
                message, MessageStatus.FAILED, error_msg
            )
            
        # Convert message to Teams webhook format
        payload = message.to_teams_payload()
        
        # Initialize retry counter and success flag
        attempts = 0
        success = False
        
        while attempts <= retry_count and not success:
            attempts += 1
            
            try:
                # Add slight delay to respect rate limits
                if attempts > 1:
                    await asyncio.sleep(retry_delay * (attempts - 1))  # Exponential backoff
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        str(webhook_config.url),
                        json=payload,
                        timeout=timeout
                    )
                    
                # Check for success (HTTP 200 OK)
                if response.status_code == 200:
                    success = True
                    return self._update_message_status(
                        message, MessageStatus.DELIVERED
                    )
                    
                # Handle different error status codes
                error_msg = f"HTTP error {response.status_code}: {response.text}"
                logger.warning(f"Attempt {attempts}/{retry_count + 1} failed: {error_msg}")
                
                # Update status to retrying if more attempts are available
                if attempts <= retry_count:
                    message = self._update_message_status(
                        message, MessageStatus.RETRYING, error_msg
                    )
                    
            except (httpx.RequestError, httpx.TimeoutException) as e:
                error_msg = f"Request error: {str(e)}"
                logger.warning(f"Attempt {attempts}/{retry_count + 1} failed: {error_msg}")
                
                # Update status to retrying if more attempts are available
                if attempts <= retry_count:
                    message = self._update_message_status(
                        message, MessageStatus.RETRYING, error_msg
                    )
        
        # If all attempts failed, mark as failed
        if not success:
            return self._update_message_status(
                message, MessageStatus.FAILED,
                f"Failed after {attempts} attempts. Last error: {message.error_message}"
            )
            
        return message