"""
MCP server implementation for MS Teams webhook integration.

This module provides the MCP server implementation for MS Teams webhook integration,
including tool registration, request handling, and server lifecycle management.
"""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Union

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool

import sys
import os

# Add the src directory to the Python path
module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if module_path not in sys.path:
    sys.path.append(module_path)
    
from mcp_teams_webhook.models.base import WebhookConfig
from mcp_teams_webhook.models.messages import AdaptiveCard, NotificationMessage, TextMessage
from mcp_teams_webhook.preprocessing.teams import TeamsMessageProcessor
from mcp_teams_webhook.teams.client import TeamsWebhookClient
from mcp_teams_webhook.teams.config import TeamsWebhookConfig

# Configure logging
logger = logging.getLogger("mcp-teams-webhook")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


@dataclass
class AppContext:
    """Application context for MCP Teams Webhook."""

    teams_client: TeamsWebhookClient
    message_processor: TeamsMessageProcessor


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[AppContext]:
    """
    Initialize and clean up application resources.
    
    Args:
        server: The MCP server instance
        
    Yields:
        Application context with initialized resources
    """
    try:
        # Initialize services
        config = TeamsWebhookConfig.from_env()
        teams_client = TeamsWebhookClient(config)
        message_processor = TeamsMessageProcessor()
        
        # Log the startup information
        logger.info("Starting MCP Teams Webhook server")
        default_webhook = config.get_webhook()
        if default_webhook:
            logger.info(f"Default webhook: {default_webhook.name}")
            logger.info(f"Total webhooks configured: {len(config.webhooks)}")
        else:
            logger.warning("No webhooks configured")
        
        # Provide context to the application
        yield AppContext(teams_client=teams_client, message_processor=message_processor)
    finally:
        # Cleanup resources if needed
        pass


# Create server instance
app = Server("mcp-teams-webhook", lifespan=server_lifespan)


# Implement server handlers
@app.list_resources()
async def list_resources() -> list[Resource]:
    """List configured MS Teams webhooks as resources."""
    resources = []
    
    ctx = app.request_context.lifespan_context
    
    # Add configured webhooks as resources
    if ctx and ctx.teams_client and ctx.teams_client.config:
        for name, webhook in ctx.teams_client.config.webhooks.items():
            resources.append(
                Resource(
                    uri=f"msteams://{name}",
                    name=f"MS Teams Webhook: {name}",
                    mimeType="text/plain",
                    description=(
                        f"MS Teams webhook for sending messages. "
                        f"Status: {webhook.status}. "
                        f"{webhook.description or ''}"
                    ).strip(),
                )
            )
    
    return resources


@app.read_resource()
async def read_resource(uri: str) -> tuple[str, str]:
    """Read content about a specific MS Teams webhook."""
    ctx = app.request_context.lifespan_context
    
    if not uri.startswith("msteams://"):
        raise ValueError(f"Invalid resource URI: {uri}")
        
    webhook_name = uri.replace("msteams://", "")
    
    # Verify we have the webhook
    if not ctx or not ctx.teams_client:
        raise ValueError("Teams client not initialized")
        
    webhook = ctx.teams_client.config.get_webhook(webhook_name)
    if not webhook:
        raise ValueError(f"Webhook not found: {webhook_name}")
    
    # Get information about the webhook
    result = await ctx.teams_client.verify_webhook(webhook_name)
    
    markdown = f"# MS Teams Webhook: {webhook.name}\n\n"
    markdown += f"**Status:** {webhook.status}\n\n"
    
    if webhook.description:
        markdown += f"**Description:** {webhook.description}\n\n"
        
    markdown += f"**Created:** {webhook.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    if webhook.updated_at:
        markdown += f"**Last Updated:** {webhook.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
    markdown += f"**Verification Result:** {result['message']}\n\n"
    
    if webhook.error_message:
        markdown += f"**Last Error:** {webhook.error_message}\n\n"
    
    return markdown, "text/markdown"


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MS Teams webhook tools."""
    tools = [
        Tool(
            name="teams_send_message",
            description="Send a text message to a Microsoft Teams channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The message text content. Supports markdown formatting by default.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title for the message",
                    },
                    "subtitle": {
                        "type": "string",
                        "description": "Optional subtitle for the message",
                    },
                    "use_markdown": {
                        "type": "boolean",
                        "description": "Whether to render text as markdown",
                        "default": True,
                    },
                    "webhook_name": {
                        "type": "string",
                        "description": "Optional name of the webhook to use. If not provided, the default webhook will be used.",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="teams_send_adaptive_card",
            description="Send an Adaptive Card to a Microsoft Teams channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Optional card title (appears outside the card)",
                    },
                    "card_elements": {
                        "type": "string",
                        "description": "JSON string of Adaptive Card elements array",
                    },
                    "card_actions": {
                        "type": "string",
                        "description": "Optional JSON string of Adaptive Card actions array",
                    },
                    "fallback_text": {
                        "type": "string",
                        "description": "Text to display if the client doesn't support Adaptive Cards",
                    },
                    "webhook_name": {
                        "type": "string",
                        "description": "Optional name of the webhook to use. If not provided, the default webhook will be used.",
                    },
                },
                "required": ["card_elements"],
            },
        ),
        Tool(
            name="teams_send_notification",
            description="Send a notification message to a Microsoft Teams channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Notification title",
                    },
                    "message": {
                        "type": "string",
                        "description": "Notification message content",
                    },
                    "priority": {
                        "type": "string",
                        "description": "Message priority level",
                        "enum": ["normal", "important", "urgent"],
                        "default": "important",
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Optional URL to an image to display with the notification",
                    },
                    "actions": {
                        "type": "string",
                        "description": "Optional JSON string of action buttons for the notification",
                    },
                    "facts": {
                        "type": "string",
                        "description": "Optional JSON string of key-value pairs to display (format: [{\"name\": \"key\", \"value\": \"value\"}])",
                    },
                    "color": {
                        "type": "string",
                        "description": "Optional color accent for the notification (hex code without #)",
                    },
                    "webhook_name": {
                        "type": "string",
                        "description": "Optional name of the webhook to use. If not provided, the default webhook will be used.",
                    },
                },
                "required": ["title", "message"],
            },
        ),
        Tool(
            name="teams_webhook_status",
            description="Check the status and connectivity of a Teams webhook",
            inputSchema={
                "type": "object",
                "properties": {
                    "webhook_name": {
                        "type": "string",
                        "description": "Optional name of the webhook to check. If not provided, the default webhook will be checked.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="teams_add_webhook",
            description="Add a new Teams webhook configuration",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Unique name for this webhook configuration",
                    },
                    "url": {
                        "type": "string",
                        "description": "MS Teams incoming webhook URL",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of this webhook's purpose",
                    },
                    "is_default": {
                        "type": "boolean",
                        "description": "Whether this should be the default webhook",
                        "default": False,
                    },
                },
                "required": ["name", "url"],
            },
        ),
    ]
    
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """
    Handle tool calls for MS Teams webhook operations.
    
    Args:
        name: Tool name
        arguments: Tool arguments
        
    Returns:
        Tool execution results
    """
    ctx = app.request_context.lifespan_context
    
    if not ctx or not ctx.teams_client:
        return [TextContent(type="text", text="Error: Teams client not initialized")]
    
    try:
        # Helper function for formatting results
        def format_result(success: bool, message: str, data: Any = None) -> TextContent:
            """Format a result as JSON."""
            result = {
                "success": success,
                "message": message,
            }
            
            if data is not None:
                result["data"] = data
                
            return TextContent(
                type="text",
                text=json.dumps(result, indent=2, ensure_ascii=False),
            )

        # Handle teams_send_message
        if name == "teams_send_message":
            text = arguments.get("text")
            title = arguments.get("title")
            subtitle = arguments.get("subtitle")
            use_markdown = arguments.get("use_markdown", True)
            webhook_name = arguments.get("webhook_name")
            
            # Create and process the message
            message = ctx.teams_client.create_text_message(
                text=text,
                title=title,
                subtitle=subtitle,
                use_markdown=use_markdown,
                webhook_name=webhook_name,
            )
            
            # Apply preprocessing
            message = ctx.message_processor.process(message)
            
            # Send the message
            result = await ctx.teams_client.send(message)
            
            # Return result
            if result.status == "delivered":
                return [format_result(
                    True,
                    "Message sent successfully",
                    {"message_id": id(result)}
                )]
            else:
                return [format_result(
                    False,
                    f"Failed to send message: {result.error_message}",
                    {"status": result.status}
                )]
        
        # Handle teams_send_adaptive_card
        elif name == "teams_send_adaptive_card":
            title = arguments.get("title")
            webhook_name = arguments.get("webhook_name")
            fallback_text = arguments.get("fallback_text")
            
            # Parse card elements from JSON string
            try:
                card_elements = json.loads(arguments.get("card_elements", "[]"))
                if not isinstance(card_elements, list):
                    raise ValueError("card_elements must be a JSON array")
            except json.JSONDecodeError:
                return [format_result(
                    False,
                    "Invalid JSON format for card_elements"
                )]
            
            # Parse card actions from JSON string if provided
            card_actions = None
            if arguments.get("card_actions"):
                try:
                    card_actions = json.loads(arguments.get("card_actions"))
                    if not isinstance(card_actions, list):
                        raise ValueError("card_actions must be a JSON array")
                except json.JSONDecodeError:
                    return [format_result(
                        False,
                        "Invalid JSON format for card_actions"
                    )]
            
            # Create and process the message
            message = ctx.teams_client.create_adaptive_card(
                card_elements=card_elements,
                title=title,
                card_actions=card_actions,
                fallback_text=fallback_text,
                webhook_name=webhook_name,
            )
            
            # Apply preprocessing
            message = ctx.message_processor.process(message)
            
            # Send the message
            result = await ctx.teams_client.send(message)
            
            # Return result
            if result.status == "delivered":
                return [format_result(
                    True,
                    "Adaptive Card sent successfully",
                    {"message_id": id(result)}
                )]
            else:
                return [format_result(
                    False,
                    f"Failed to send Adaptive Card: {result.error_message}",
                    {"status": result.status}
                )]
        
        # Handle teams_send_notification
        elif name == "teams_send_notification":
            title = arguments.get("title")
            message_text = arguments.get("message")
            priority = arguments.get("priority", "important")
            image_url = arguments.get("image_url")
            webhook_name = arguments.get("webhook_name")
            color = arguments.get("color")
            
            # Parse actions from JSON string if provided
            actions = []
            if arguments.get("actions"):
                try:
                    actions = json.loads(arguments.get("actions"))
                    if not isinstance(actions, list):
                        raise ValueError("actions must be a JSON array")
                except json.JSONDecodeError:
                    return [format_result(
                        False,
                        "Invalid JSON format for actions"
                    )]
            
            # Parse facts from JSON string if provided
            facts = None
            if arguments.get("facts"):
                try:
                    facts = json.loads(arguments.get("facts"))
                    if not isinstance(facts, list):
                        raise ValueError("facts must be a JSON array")
                except json.JSONDecodeError:
                    return [format_result(
                        False,
                        "Invalid JSON format for facts"
                    )]
            
            # Create and process the message
            message = ctx.teams_client.create_notification(
                title=title,
                message=message_text,
                image_url=image_url,
                actions=actions,
                facts=facts,
                color=color,
                webhook_name=webhook_name,
            )
            
            # Set priority
            if priority in ["normal", "important", "urgent"]:
                message.priority = priority
            
            # Apply preprocessing
            message = ctx.message_processor.process(message)
            
            # Send the message
            result = await ctx.teams_client.send(message)
            
            # Return result
            if result.status == "delivered":
                return [format_result(
                    True,
                    "Notification sent successfully",
                    {"message_id": id(result)}
                )]
            else:
                return [format_result(
                    False,
                    f"Failed to send notification: {result.error_message}",
                    {"status": result.status}
                )]
        
        # Handle teams_webhook_status
        elif name == "teams_webhook_status":
            webhook_name = arguments.get("webhook_name")
            
            # Check webhook status
            result = await ctx.teams_client.verify_webhook(webhook_name)
            
            # Get the webhook details
            webhook = ctx.teams_client.config.get_webhook(webhook_name)
            
            # Return results
            return [format_result(
                result.get("valid", False),
                result.get("message", "Unknown status"),
                {
                    "webhook_name": webhook_name or (webhook.name if webhook else "default"),
                    "status": result.get("status"),
                    "is_default": webhook.is_default if webhook else False,
                    "created_at": webhook.created_at.isoformat() if webhook else None,
                    "updated_at": webhook.updated_at.isoformat() if webhook and webhook.updated_at else None,
                }
            )]
        
        # Handle teams_add_webhook
        elif name == "teams_add_webhook":
            name = arguments.get("name")
            url = arguments.get("url")
            description = arguments.get("description")
            is_default = arguments.get("is_default", False)
            
            # Create webhook configuration
            webhook = WebhookConfig(
                name=name,
                url=url,
                description=description,
                is_default=is_default,
            )
            
            # Add to configuration
            success = ctx.teams_client.config.add_webhook(webhook, save=True)
            
            if success:
                return [format_result(
                    True,
                    f"Webhook '{name}' added successfully",
                    {"webhook_name": name, "is_default": is_default}
                )]
            else:
                return [format_result(
                    False,
                    f"Failed to add webhook '{name}'"
                )]
        
        # Handle unknown tool
        return [format_result(
            False,
            f"Unknown tool: {name}"
        )]
    
    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def run_server(transport: str = "stdio", port: int = 8000) -> None:
    """
    Run the MCP Teams Webhook server with the specified transport.
    
    Args:
        transport: Transport type ("stdio" or "sse")
        port: Port number for SSE transport
    """
    if transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.routing import Mount, Route
        
        sse = SseServerTransport("/messages/")
        
        async def handle_sse(request: Request) -> None:
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await app.run(
                    streams[0], streams[1], app.create_initialization_options()
                )
        
        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )
        
        import uvicorn
        
        # Set up uvicorn config
        config = uvicorn.Config(starlette_app, host="0.0.0.0", port=port)
        server = uvicorn.Server(config)
        # Use server.serve() instead of run() to stay in the same event loop
        await server.serve()
    else:
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )