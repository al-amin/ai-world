"""
Constants for the MCP MS Teams Webhook models.

This module provides constants used throughout the MCP MS Teams Webhook models,
such as empty values, default settings, and message limits.
"""

# Empty values
EMPTY_STRING = ""
EMPTY_DICT = {}
EMPTY_LIST = []

# MS Teams limits
MAX_MESSAGE_SIZE_BYTES = 28 * 1024  # 28 KB
MAX_REQUESTS_PER_SECOND = 4

# Default values
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_REQUEST_TIMEOUT = 10.0  # seconds

# Webhook status
WEBHOOK_STATUS_ACTIVE = "active"
WEBHOOK_STATUS_INACTIVE = "inactive"
WEBHOOK_STATUS_ERROR = "error"

# Message types
MESSAGE_TYPE_TEXT = "text"
MESSAGE_TYPE_ADAPTIVE_CARD = "adaptive_card"
MESSAGE_TYPE_NOTIFICATION = "notification"

# Message priorities
PRIORITY_NORMAL = "normal"
PRIORITY_IMPORTANT = "important"
PRIORITY_URGENT = "urgent"

# Message status
MESSAGE_STATUS_PENDING = "pending"
MESSAGE_STATUS_DELIVERED = "delivered"
MESSAGE_STATUS_FAILED = "failed"
MESSAGE_STATUS_RETRYING = "retrying"