"""
MS Teams specific preprocessing functionality.

This module provides preprocessing utilities specific to MS Teams messages,
including adaptive card validation and content sanitization.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from ..models.base import MessageBase
from ..models.messages import AdaptiveCard, NotificationMessage, TextMessage
from .base import MessagePreprocessor, SecurityPreprocessor, SizeLimitPreprocessor

# Configure logging
logger = logging.getLogger("mcp-teams-webhook")


class AdaptiveCardPreprocessor(MessagePreprocessor):
    """Preprocessor for Adaptive Cards to ensure compatibility with MS Teams."""
    
    def process(self, message: MessageBase) -> MessageBase:
        """
        Process an Adaptive Card to ensure it's compatible with MS Teams.
        
        Args:
            message: The message to process
            
        Returns:
            The processed message
        """
        if not isinstance(message, AdaptiveCard):
            return message
            
        # Validate and fix card elements
        valid_elements = []
        for element in message.card_elements:
            processed_element = self._validate_card_element(element)
            if processed_element:
                valid_elements.append(processed_element)
                
        message.card_elements = valid_elements
        
        # Validate and fix card actions
        if message.card_actions:
            valid_actions = []
            for action in message.card_actions:
                processed_action = self._validate_card_action(action)
                if processed_action:
                    valid_actions.append(processed_action)
                    
            message.card_actions = valid_actions
            
        return message
        
    def _validate_card_element(self, element: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate and fix a card element for MS Teams compatibility.
        
        Args:
            element: The card element to validate
            
        Returns:
            The validated element or None if invalid
        """
        if not isinstance(element, dict) or "type" not in element:
            logger.warning("Invalid card element: missing type")
            return None
            
        element_type = element["type"]
        
        # Validate known element types
        if element_type == "TextBlock":
            # Ensure text is present
            if "text" not in element:
                logger.warning("TextBlock missing required 'text' property")
                element["text"] = ""
                
        elif element_type == "Image":
            # Ensure url is present
            if "url" not in element:
                logger.warning("Image missing required 'url' property")
                return None
                
        elif element_type == "FactSet":
            # Ensure facts array is present
            if "facts" not in element or not isinstance(element["facts"], list):
                logger.warning("FactSet missing required 'facts' array")
                element["facts"] = []
                
        elif element_type == "Input.Text":
            # Ensure id is present
            if "id" not in element:
                logger.warning("Input.Text missing required 'id' property")
                return None
                
        # Return the validated element
        return element
        
    def _validate_card_action(self, action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate and fix a card action for MS Teams compatibility.
        
        Args:
            action: The card action to validate
            
        Returns:
            The validated action or None if invalid
        """
        if not isinstance(action, dict) or "type" not in action:
            logger.warning("Invalid card action: missing type")
            return None
            
        action_type = action["type"]
        
        # Validate known action types
        if action_type == "Action.OpenUrl":
            # Ensure url is present
            if "url" not in action:
                logger.warning("Action.OpenUrl missing required 'url' property")
                return None
                
            # Ensure title is present
            if "title" not in action:
                logger.warning("Action.OpenUrl missing required 'title' property")
                action["title"] = "Open URL"
                
        elif action_type == "Action.Submit":
            # Ensure data is present
            if "data" not in action:
                logger.warning("Action.Submit missing 'data' property")
                action["data"] = {}
                
            # Ensure title is present
            if "title" not in action:
                logger.warning("Action.Submit missing required 'title' property")
                action["title"] = "Submit"
                
        # Only allow supported actions in MS Teams
        elif action_type not in ["Action.ShowCard", "Action.ToggleVisibility"]:
            logger.warning(f"Unsupported action type for MS Teams: {action_type}")
            return None
            
        # Return the validated action
        return action


class NotificationPreprocessor(MessagePreprocessor):
    """Preprocessor for notification messages to ensure compatibility with MS Teams."""
    
    def process(self, message: MessageBase) -> MessageBase:
        """
        Process a notification message for MS Teams compatibility.
        
        Args:
            message: The message to process
            
        Returns:
            The processed message
        """
        if not isinstance(message, NotificationMessage):
            return message
            
        # Validate and format facts
        if message.facts:
            valid_facts = []
            for fact in message.facts:
                if isinstance(fact, dict) and "name" in fact and "value" in fact:
                    valid_facts.append(fact)
                elif isinstance(fact, dict) and len(fact) == 1:
                    # Convert single key-value pair to name/value format
                    for key, value in fact.items():
                        valid_facts.append({"name": key, "value": str(value)})
                        
            message.facts = valid_facts
            
        # Validate actions
        if message.actions:
            valid_actions = []
            for action in message.actions:
                if isinstance(action, dict) and "type" in action:
                    # Ensure the action has required properties
                    if action["type"] == "ViewAction" and "name" in action and "target" in action:
                        valid_actions.append(action)
                    elif action["type"] == "ActionCard" and "name" in action and "actions" in action:
                        valid_actions.append(action)
                        
            message.actions = valid_actions
            
        return message


class TeamsMessageProcessor:
    """
    Combines multiple preprocessors to prepare messages for MS Teams.
    
    This processor applies a chain of preprocessors to ensure messages are
    secure, valid, and within size limits for MS Teams webhooks.
    """
    
    def __init__(self):
        """Initialize the processor with a chain of preprocessors."""
        self._preprocessors = [
            SecurityPreprocessor(),  # First, sanitize content
            AdaptiveCardPreprocessor(),  # Then, validate adaptive cards
            NotificationPreprocessor(),  # Then, validate notifications
            SizeLimitPreprocessor(),  # Finally, ensure within size limits
        ]
        
    def process(self, message: MessageBase) -> MessageBase:
        """
        Process a message through all preprocessors.
        
        Args:
            message: The message to process
            
        Returns:
            The fully processed message
        """
        result = message
        
        for preprocessor in self._preprocessors:
            result = preprocessor.process(result)
            
        return result