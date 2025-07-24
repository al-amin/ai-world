#!/usr/bin/env python3
"""
Example script demonstrating how to use the MCP MS Teams Webhook server.

This script shows how to manually create and send messages to MS Teams
using the client classes directly.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent / "src"))

from mcp_teams_webhook.models.base import WebhookConfig, WebhookStatus
from mcp_teams_webhook.teams.client import TeamsWebhookClient
from mcp_teams_webhook.teams.config import TeamsWebhookConfig


async def main():
    """Run example MS Teams webhook integration."""
    print("MCP MS Teams Webhook Example")
    print("-" * 30)

    # Create webhook configuration
    # Option 1: From environment variables
    # os.environ["TEAMS_WEBHOOK_URL"] = "https://your-webhook-url"
    # config = TeamsWebhookConfig.from_env()

    # Option 2: From file
    config_file = Path(__file__).parent / "sample_config.json"
    if config_file.exists():
        print(f"Loading config from {config_file}")
        config = TeamsWebhookConfig.from_file(str(config_file))
    else:
        print("Creating empty config")
        config = TeamsWebhookConfig()

    # Option 3: Manual configuration
    if not config.webhooks:
        print("Adding sample webhook")
        webhook = WebhookConfig(
            name="example",
            url="https://outlook.office.com/webhook/your-webhook-id/IncomingWebhook/your-webhook-path",
            description="Example webhook",
            is_default=True,
        )
        config.add_webhook(webhook, save=False)

    # Create client
    client = TeamsWebhookClient(config)

    # List available webhooks
    print("\nConfigured webhooks:")
    for name, webhook in config.webhooks.items():
        print(f"- {name}: {webhook.url} (default: {webhook.is_default})")

    # Example 1: Send text message
    print("\nExample 1: Sending text message...")
    text_message = client.create_text_message(
        text="Hello from MCP MS Teams Webhook!\n\n"
        "This is an example message with:\n"
        "- Markdown formatting\n"
        "- Multiple lines\n\n"
        "**Bold text** and *italic text*",
        title="Example Message",
    )

    # We would send the message here, but we're not sending real requests in the example
    print(json.dumps(text_message.to_teams_payload(), indent=2))

    # Example 2: Create adaptive card
    print("\nExample 2: Creating adaptive card...")
    card_elements = [
        {
            "type": "TextBlock",
            "text": "MCP MS Teams Webhook",
            "weight": "Bolder",
            "size": "Medium"
        },
        {
            "type": "TextBlock",
            "text": "Example adaptive card message",
            "wrap": True
        },
        {
            "type": "FactSet",
            "facts": [
                {
                    "title": "Created by",
                    "value": "MCP MS Teams Webhook"
                },
                {
                    "title": "Status",
                    "value": "Active"
                }
            ]
        }
    ]

    card_actions = [
        {
            "type": "Action.OpenUrl",
            "title": "View Documentation",
            "url": "https://github.com/your-repo/MCP-MS-TEAMS-WEBHOOK"
        }
    ]

    adaptive_card = client.create_adaptive_card(
        card_elements=card_elements,
        card_actions=card_actions,
        title="Example Adaptive Card",
        fallback_text="Your client doesn't support Adaptive Cards.",
    )

    # We would send the message here, but we're not sending real requests in the example
    print(json.dumps(adaptive_card.to_teams_payload(), indent=2))

    # Example 3: Create notification
    print("\nExample 3: Creating notification...")
    notification = client.create_notification(
        title="System Alert",
        message="Server CPU usage is above 90%",
        facts=[
            {"name": "Server", "value": "web-server-01"},
            {"name": "CPU Usage", "value": "92%"},
            {"name": "Memory", "value": "6.2GB / 8GB"},
        ],
        color="FF0000",  # Red
    )
    # Set priority after creation since it's not in the constructor
    notification.priority = "urgent"

    # We would send the message here, but we're not sending real requests in the example
    print(json.dumps(notification.to_teams_payload(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())