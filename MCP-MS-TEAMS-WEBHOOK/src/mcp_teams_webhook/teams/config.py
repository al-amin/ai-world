"""
Configuration management for MS Teams webhook integration.

This module provides classes for managing webhook configurations, including
loading from environment variables or configuration files.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from dotenv import load_dotenv
from pydantic import BaseModel

from ..models.base import WebhookConfig
from ..models.constants import EMPTY_DICT, EMPTY_LIST, EMPTY_STRING

# Configure logging
logger = logging.getLogger("mcp-teams-webhook")


class TeamsWebhookConfig(BaseModel):
    """
    Configuration for MS Teams webhook integration.
    
    Manages webhook configurations and provides methods for loading and saving
    webhook configuration data.
    """

    default_webhook_name: Optional[str] = None
    webhooks: Dict[str, WebhookConfig] = {}
    config_file: Optional[str] = None

    @classmethod
    def from_env(cls) -> "TeamsWebhookConfig":
        """
        Load configuration from environment variables.

        Returns:
            A new TeamsWebhookConfig instance with environment settings
        """
        load_dotenv()
        
        # Check for a configuration file path
        config_file = os.getenv("TEAMS_WEBHOOK_CONFIG_FILE")
        
        # If config file exists, load from it
        if config_file and Path(config_file).exists():
            return cls.from_file(config_file)
            
        # Otherwise, try to load directly from environment variables
        webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
        if not webhook_url:
            logger.warning("No TEAMS_WEBHOOK_URL environment variable found")
            return cls()
            
        # Create a simple configuration with a single default webhook
        webhook_name = os.getenv("TEAMS_WEBHOOK_NAME", "default")
        webhook_description = os.getenv("TEAMS_WEBHOOK_DESCRIPTION", "Default webhook from environment variables")
        
        webhook = WebhookConfig(
            name=webhook_name,
            url=webhook_url,
            description=webhook_description,
            is_default=True
        )
        
        return cls(
            default_webhook_name=webhook_name,
            webhooks={webhook_name: webhook},
            config_file=config_file
        )
    
    @classmethod
    def from_file(cls, file_path: str) -> "TeamsWebhookConfig":
        """
        Load configuration from a JSON file.

        Args:
            file_path: Path to the configuration file

        Returns:
            A new TeamsWebhookConfig instance with settings from the file
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                
            # Initialize empty configuration
            config = cls(config_file=file_path)
            
            # Load webhook configurations
            if "webhooks" in config_data and isinstance(config_data["webhooks"], list):
                for webhook_data in config_data["webhooks"]:
                    webhook = WebhookConfig(**webhook_data)
                    config.webhooks[webhook.name] = webhook
                    
                    # Set as default if marked or if it's the only one
                    if webhook.is_default or len(config.webhooks) == 1:
                        config.default_webhook_name = webhook.name
            
            return config
            
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            logger.error(f"Error loading config from {file_path}: {str(e)}")
            return cls(config_file=file_path)
    
    def save_to_file(self, file_path: Optional[str] = None) -> bool:
        """
        Save the current configuration to a JSON file.

        Args:
            file_path: Path to save the configuration (uses self.config_file if None)

        Returns:
            True if successful, False otherwise
        """
        save_path = file_path or self.config_file
        if not save_path:
            logger.error("No file path provided for saving configuration")
            return False
            
        try:
            # Convert webhooks to serializable format
            webhook_list = [webhook.model_dump() for webhook in self.webhooks.values()]
            
            config_data = {
                "webhooks": webhook_list
            }
            
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
                
            return True
            
        except Exception as e:
            logger.error(f"Error saving config to {save_path}: {str(e)}")
            return False
    
    def get_webhook(self, name: Optional[str] = None) -> Optional[WebhookConfig]:
        """
        Get a webhook configuration by name.

        Args:
            name: Name of the webhook to retrieve (uses default if None)

        Returns:
            WebhookConfig if found, None otherwise
        """
        webhook_name = name or self.default_webhook_name
        
        if not webhook_name:
            # No webhook name provided and no default set
            if self.webhooks:
                # Return the first webhook if any exist
                return next(iter(self.webhooks.values()))
            return None
            
        return self.webhooks.get(webhook_name)
    
    def add_webhook(self, webhook: WebhookConfig, save: bool = True) -> bool:
        """
        Add a new webhook configuration.

        Args:
            webhook: WebhookConfig to add
            save: Whether to save to file after adding

        Returns:
            True if successful, False otherwise
        """
        # Add the webhook to the configuration
        self.webhooks[webhook.name] = webhook
        
        # Set as default if marked or if it's the only one
        if webhook.is_default or len(self.webhooks) == 1:
            self.default_webhook_name = webhook.name
            
        # Save to file if requested
        if save and self.config_file:
            return self.save_to_file()
            
        return True
        
    def remove_webhook(self, name: str, save: bool = True) -> bool:
        """
        Remove a webhook configuration by name.

        Args:
            name: Name of the webhook to remove
            save: Whether to save to file after removing

        Returns:
            True if successful, False otherwise
        """
        if name not in self.webhooks:
            return False
            
        # Remove the webhook
        del self.webhooks[name]
        
        # Update default if needed
        if self.default_webhook_name == name:
            if self.webhooks:
                # Set a new default if any webhooks remain
                self.default_webhook_name = next(iter(self.webhooks.keys()))
            else:
                self.default_webhook_name = None
                
        # Save to file if requested
        if save and self.config_file:
            return self.save_to_file()
            
        return True