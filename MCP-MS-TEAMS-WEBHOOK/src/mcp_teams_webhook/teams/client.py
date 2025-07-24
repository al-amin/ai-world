"""
MS Teams webhook client implementation.

This module provides the main client class for the MS Teams webhook integration,
combining various mixins to create a full-featured client.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union

import httpx

from ..models.base import MessageBase, MessageStatus, WebhookConfig
from ..models.constants import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY,
    WEBHOOK_STATUS_ACTIVE,
    WEBHOOK_STATUS_ERROR,
)
from ..models.messages import AdaptiveCard, NotificationMessage, TextMessage
from .config import TeamsWebhookConfig
from .message import (
    AdaptiveCardMixin,
    MessageDeliveryMixin,
    NotificationMixin,
    TextMessageMixin,
)

# Configure logging
logger = logging.getLogger("mcp-teams-webhook")


class TeamsWebhookClient(
    TextMessageMixin,
    AdaptiveCardMixin,
    NotificationMixin,
    MessageDeliveryMixin,
):
    """
    Client for interacting with MS Teams webhooks.
    
    Combines functionality from various mixins to provide a complete client
    for creating and sending messages to MS Teams webhooks.
    """

    def __init__(self, config: Optional[TeamsWebhookConfig] = None):
        """
        Initialize the Teams webhook client.

        Args:
            config: Optional webhook configuration (loads from env if None)
        """
        self.config = config or TeamsWebhookConfig.from_env()
        self._message_history: List[MessageBase] = []
        self._last_message_timestamp: Optional[datetime] = None
        self._message_count_in_window = 0
        self._rate_limit_window = 1.0  # 1 second window for rate limiting

    async def verify_webhook(
        self, webhook_name: Optional[str] = None, timeout: float = DEFAULT_REQUEST_TIMEOUT
    ) -> Dict[str, bool | str]:
        """
        Verify that a webhook is valid and working.

        Args:
            webhook_name: Name of the webhook to verify (uses default if None)
            timeout: Request timeout in seconds

        Returns:
            Dictionary with verification results
        """
        webhook = self.config.get_webhook(webhook_name)
        if not webhook:
            return {
                "valid": False,
                "status": "error",
                "message": f"Webhook configuration not found: {webhook_name or 'default'}",
            }
            
        try:
            # Send a simple ping message to verify the webhook
            test_message = self.create_text_message(
                text="Webhook verification test. If you see this message, the webhook is working correctly.",
                title="Webhook Test",
                webhook_name=webhook_name,
            )
            
            # Send the message with a single attempt and short timeout
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    str(webhook.url),
                    json=test_message.to_teams_payload(),
                    timeout=timeout
                )
                
            if response.status_code == 200:
                # Update webhook status if needed
                if webhook.status != WEBHOOK_STATUS_ACTIVE:
                    webhook.status = WEBHOOK_STATUS_ACTIVE
                    webhook.error_message = None
                    webhook.updated_at = datetime.now()
                    self.config.save_to_file()
                    
                return {
                    "valid": True,
                    "status": "active",
                    "message": "Webhook is active and working correctly",
                }
            else:
                # Update webhook status to error
                webhook.status = WEBHOOK_STATUS_ERROR
                webhook.error_message = f"HTTP error {response.status_code}: {response.text}"
                webhook.updated_at = datetime.now()
                self.config.save_to_file()
                
                return {
                    "valid": False,
                    "status": "error",
                    "message": webhook.error_message,
                }
                
        except Exception as e:
            # Update webhook status to error
            webhook.status = WEBHOOK_STATUS_ERROR
            webhook.error_message = str(e)
            webhook.updated_at = datetime.now()
            self.config.save_to_file()
            
            return {
                "valid": False,
                "status": "error",
                "message": str(e),
            }

    async def send(
        self,
        message: MessageBase,
        webhook_name: Optional[str] = None,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        retry_count: int = DEFAULT_RETRY_COUNT,
    ) -> MessageBase:
        """
        Send a message to an MS Teams webhook.

        Args:
            message: The message to send
            webhook_name: Name of the webhook to use (overrides message.webhook_name)
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure

        Returns:
            The message with updated status
        """
        # Get the webhook to use
        webhook_to_use = webhook_name or message.webhook_name
        webhook = self.config.get_webhook(webhook_to_use)
        
        if not webhook:
            error_msg = f"Webhook configuration not found: {webhook_to_use or 'default'}"
            logger.error(error_msg)
            message.status = MessageStatus.FAILED
            message.error_message = error_msg
            return message
            
        # Check webhook status
        if webhook.status == WEBHOOK_STATUS_ERROR:
            # Attempt to verify the webhook first
            verify_result = await self.verify_webhook(webhook_to_use, timeout)
            if not verify_result["valid"]:
                error_msg = f"Webhook is in error state: {verify_result['message']}"
                logger.error(error_msg)
                message.status = MessageStatus.FAILED
                message.error_message = error_msg
                return message
        
        # Track for rate limiting purposes
        now = datetime.now()
        if (self._last_message_timestamp and 
            (now - self._last_message_timestamp).total_seconds() < self._rate_limit_window):
            # Still within the rate limit window
            self._message_count_in_window += 1
        else:
            # New rate limit window
            self._message_count_in_window = 1
            
        self._last_message_timestamp = now
        
        # Apply rate limiting if needed
        delay = self._get_rate_limit_delay(self._message_count_in_window, self._rate_limit_window)
        if delay > 0:
            logger.debug(f"Rate limiting applied. Waiting {delay:.2f} seconds.")
            await asyncio.sleep(delay)
            # Reset counter after waiting
            self._message_count_in_window = 1
            self._last_message_timestamp = datetime.now()
            
        # Send the message
        result = await self.send_message(
            message,
            webhook,
            timeout=timeout,
            retry_count=retry_count,
            retry_delay=DEFAULT_RETRY_DELAY,
        )
        
        # Store in history
        self._message_history.append(result)
        
        # Limit history size
        if len(self._message_history) > 100:
            self._message_history = self._message_history[-100:]
            
        return result
        
    def get_message_history(self) -> List[MessageBase]:
        """
        Get the history of sent messages.

        Returns:
            List of sent messages with their status
        """
        return self._message_history