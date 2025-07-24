"""
Base preprocessing functionality for MS Teams webhook integration.

This module provides base classes for preprocessing message content and
adaptive cards before sending to MS Teams.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Union, Generic

from ..models.base import MessageBase
from ..models.constants import MAX_MESSAGE_SIZE_BYTES

# Configure logging
logger = logging.getLogger("mcp-teams-webhook")

# Type variable for preprocessor input types
T = TypeVar("T")
U = TypeVar("U")


class Preprocessor(ABC, Generic[T, U]):
    """
    Base class for all preprocessors.
    
    Preprocessors transform input data before it's sent to MS Teams.
    """
    
    @abstractmethod
    def process(self, data: T) -> U:
        """
        Process the input data.
        
        Args:
            data: Input data to process
            
        Returns:
            Processed data
        """
        pass


class MessagePreprocessor(Preprocessor[MessageBase, MessageBase]):
    """Base preprocessor for message content."""
    
    def process(self, message: MessageBase) -> MessageBase:
        """
        Process a message before sending to MS Teams.
        
        Args:
            message: The message to process
            
        Returns:
            The processed message
        """
        # Default implementation simply returns the original message
        return message


class SizeLimitPreprocessor(MessagePreprocessor):
    """Preprocessor to ensure messages are within size limits."""
    
    def process(self, message: MessageBase) -> MessageBase:
        """
        Ensure the message is within MS Teams size limits.
        
        If the message is too large, it will be truncated.
        
        Args:
            message: The message to process
            
        Returns:
            The processed message
        """
        if message.validate_size():
            return message
            
        logger.warning("Message exceeds size limit, attempting to truncate")
        
        # Try to truncate text fields to fit within limits
        if hasattr(message, "text") and hasattr(message, "to_teams_payload"):
            # For text messages, truncate the text content
            current_size = len(message.model_dump_json().encode("utf-8"))
            excess_bytes = current_size - MAX_MESSAGE_SIZE_BYTES
            
            # Add a buffer to ensure we're under the limit after truncation
            truncate_bytes = excess_bytes + 100
            
            # Get the current text length in bytes
            text_bytes = len(message.text.encode("utf-8"))
            
            if text_bytes > truncate_bytes:
                # Truncate the text content
                new_text_bytes = text_bytes - truncate_bytes
                new_text = message.text.encode("utf-8")[:new_text_bytes].decode("utf-8", errors="ignore")
                
                # Add truncation indicator
                new_text = new_text + "\n... (content truncated due to size limits)"
                
                # Update the message
                message.text = new_text
                
                logger.info(f"Message truncated from {current_size} to approximately {MAX_MESSAGE_SIZE_BYTES} bytes")
                
        return message


class SecurityPreprocessor(MessagePreprocessor):
    """Preprocessor to sanitize message content for security."""
    
    def process(self, message: MessageBase) -> MessageBase:
        """
        Sanitize message content for security.
        
        Args:
            message: The message to process
            
        Returns:
            The sanitized message
        """
        # Sanitize common text fields
        if hasattr(message, "text"):
            message.text = self._sanitize_text(message.text)
            
        if hasattr(message, "title"):
            message.title = self._sanitize_text(message.title)
            
        if hasattr(message, "subtitle"):
            message.subtitle = self._sanitize_text(message.subtitle)
            
        if hasattr(message, "message"):
            message.message = self._sanitize_text(message.message)
            
        return message
        
    def _sanitize_text(self, text: Optional[str]) -> Optional[str]:
        """
        Sanitize text content to prevent injection attacks.
        
        Args:
            text: The text to sanitize
            
        Returns:
            Sanitized text
        """
        if not text:
            return text
            
        # Remove potentially harmful HTML tags (MS Teams may interpret some HTML)
        # Note: This is a simple sanitizer and not comprehensive
        sanitized = text
        
        # Replace potentially dangerous characters with safe ones
        replacements = {
            "<script": "&lt;script",
            "</script>": "&lt;/script&gt;",
            "javascript:": "blocked:",
        }
        
        for dangerous, safe in replacements.items():
            sanitized = sanitized.replace(dangerous, safe)
            
        return sanitized