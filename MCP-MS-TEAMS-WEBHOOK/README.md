# MCP MS Teams Webhook Server

A Model Context Protocol (MCP) server implementation for sending messages to Microsoft Teams channels via incoming webhooks. This server allows AI assistants to send notifications, alerts, and interactive messages to Microsoft Teams.

## Features

- Send plain text messages with markdown formatting
- Send Adaptive Card messages with interactive elements
- Send notification messages with priority levels
- Manage multiple webhook configurations
- Verify webhook connectivity
- Handle rate limiting and retries automatically
- Secure message content handling

## Installation

### From Source

```bash
# Clone the repository
git clone https://your-repository-url/MCP-MS-TEAMS-WEBHOOK.git
cd MCP-MS-TEAMS-WEBHOOK

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"
```

## Configuration

The server can be configured using environment variables or a JSON configuration file.

### Environment Variables

- `TEAMS_WEBHOOK_URL`: The URL of the MS Teams incoming webhook
- `TEAMS_WEBHOOK_NAME`: Optional name for the webhook (default: "default")
- `TEAMS_WEBHOOK_DESCRIPTION`: Optional description of the webhook
- `TEAMS_WEBHOOK_CONFIG_FILE`: Path to a JSON configuration file
- `MCP_LOG_LEVEL`: Set logging level (default: INFO)
- `PYTHONPATH`: Should include the path to the `src` directory

### Configuration File

Create a JSON file with your webhook configurations:

```json
{
  "webhooks": [
    {
      "name": "dev-team",
      "url": "https://outlook.office.com/webhook/...",
      "description": "Development team channel",
      "is_default": true
    },
    {
      "name": "alerts",
      "url": "https://outlook.office.com/webhook/...",
      "description": "Alerts channel"
    }
  ]
}
```

### VS Code Integration

To integrate with VS Code, add a configuration to your `.vscode/mcp.json` file:

```json
{
  "servers": {
    "mcp-teams-webhook": {
      "type": "stdio",
      "command": "${workspaceFolder}/venv/bin/python",
      "args": [
        "${workspaceFolder}/MCP-MS-TEAMS-WEBHOOK/run_server.py"
      ],
      "env": {
        "TEAMS_WEBHOOK_URL": "https://your-teams-webhook-url",
        "TEAMS_WEBHOOK_NAME": "your-webhook-name",
        "PYTHONPATH": "${workspaceFolder}/MCP-MS-TEAMS-WEBHOOK/src",
        "MCP_LOG_LEVEL": "DEBUG",
        "PYTHONUNBUFFERED": "1"
      },
      "cwd": "${workspaceFolder}"
    }
  }
}
```

## Running the Server

### With stdio Transport (default)

```bash
# Run directly 
python run_server.py

# Or using the module
python -m mcp_teams_webhook
```

### With SSE Transport

```bash
python -m mcp_teams_webhook --transport sse --port 8000
```

## Available Tools

The server provides the following MCP tools:

### teams_send_message

Send a text message to a Microsoft Teams channel.

**Parameters:**
- `text`: The message text content (supports markdown)
- `title`: Optional message title
- `subtitle`: Optional message subtitle
- `use_markdown`: Whether to render text as markdown (default: true)
- `webhook_name`: Optional name of the webhook to use

**Example:**
```json
{
  "text": "Hello from the MCP server!",
  "title": "MCP Notification",
  "use_markdown": true
}
```

**Message Format:**
The message is sent with a simple payload format for maximum compatibility:
```json
{
  "text": "## MCP Notification\n\nHello from the MCP server!"
}
```

### teams_send_adaptive_card

Send an Adaptive Card message to a Microsoft Teams channel.

**Parameters:**
- `title`: Optional card title
- `card_elements`: JSON string of Adaptive Card elements array
- `card_actions`: Optional JSON string of Adaptive Card actions array
- `fallback_text`: Text to display if the client doesn't support Adaptive Cards
- `webhook_name`: Optional name of the webhook to use

**Example:**
```json
{
  "title": "Adaptive Card Example",
  "card_elements": "[{\"type\":\"TextBlock\",\"text\":\"This is an adaptive card\",\"weight\":\"bolder\",\"size\":\"medium\"},{\"type\":\"TextBlock\",\"text\":\"It can contain multiple elements\",\"isSubtle\":true}]",
  "card_actions": "[{\"type\":\"Action.OpenUrl\",\"title\":\"Learn More\",\"url\":\"https://adaptivecards.io\"}]",
  "fallback_text": "This client doesn't support Adaptive Cards"
}
```

**Message Format:**
The message is sent as an attachment with proper content type:
```json
{
  "attachments": [
    {
      "contentType": "application/vnd.microsoft.card.adaptive",
      "content": {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
          {
            "type": "TextBlock",
            "text": "This is an adaptive card",
            "weight": "bolder",
            "size": "medium"
          },
          {
            "type": "TextBlock",
            "text": "It can contain multiple elements",
            "isSubtle": true
          }
        ],
        "actions": [
          {
            "type": "Action.OpenUrl",
            "title": "Learn More",
            "url": "https://adaptivecards.io"
          }
        ]
      }
    }
  ],
  "text": "Adaptive Card Example"
}
```

### teams_send_notification

Send a notification message to a Microsoft Teams channel.

**Parameters:**
- `title`: Notification title
- `message`: Notification message content
- `priority`: Message priority level (normal, important, urgent)
- `image_url`: Optional URL to an image
- `actions`: Optional JSON string of action buttons
- `facts`: Optional JSON string of key-value pairs to display
- `color`: Optional color accent for the notification (hex code)
- `webhook_name`: Optional name of the webhook to use

**Example:**
```json
{
  "title": "Important Alert",
  "message": "System performance is degraded",
  "priority": "important",
  "facts": "[{\"name\":\"Status\",\"value\":\"Degraded\"},{\"name\":\"Service\",\"value\":\"API Gateway\"}]",
  "color": "FF0000"
}
```

**Message Format:**
The message is sent using MessageCard format:
```json
{
  "@type": "MessageCard",
  "@context": "http://schema.org/extensions",
  "summary": "Important Alert",
  "themeColor": "FF0000",
  "sections": [
    {
      "activityTitle": "Important Alert",
      "activitySubtitle": "System performance is degraded",
      "facts": [
        {
          "name": "Status",
          "value": "Degraded"
        },
        {
          "name": "Service",
          "value": "API Gateway"
        }
      ]
    }
  ]
}
```

### teams_webhook_status

Check the status and connectivity of a Teams webhook.

**Parameters:**
- `webhook_name`: Optional name of the webhook to check

### teams_add_webhook

Add a new Teams webhook configuration.

**Parameters:**
- `name`: Unique name for this webhook configuration
- `url`: MS Teams incoming webhook URL
- `description`: Optional description of this webhook's purpose
- `is_default`: Whether this should be the default webhook

## Development

### Running Tests

```bash
pytest
```

### Running with Development Settings

```bash
# Set log level to DEBUG
python -m mcp_teams_webhook --log-level DEBUG
```

## Troubleshooting

### Common Issues

#### "Card - access it on https://go.skype.com/cards.unsupported" Error

This error occurs when the card format sent to MS Teams isn't compatible with the Teams webhook API. To resolve this:

1. **For text messages**: Use the simple format with just the "text" field:
   ```json
   { "text": "Your message here" }
   ```

2. **For Adaptive Cards**: Make sure to use the correct attachment format:
   ```json
   {
     "attachments": [
       {
         "contentType": "application/vnd.microsoft.card.adaptive",
         "content": { ... }
       }
     ]
   }
   ```

3. **For Notification/MessageCard**: Use the correct MessageCard format:
   ```json
   {
     "@type": "MessageCard",
     "@context": "http://schema.org/extensions",
     "summary": "...",
     "themeColor": "...",
     "sections": [ ... ]
   }
   ```

#### Module Import Errors

If you encounter import errors when running the server:

1. Make sure the PYTHONPATH environment variable includes the path to the `src` directory
2. When running from the command line, use the provided `run_server.py` script
3. Check your Python virtual environment is activated

#### Rate Limiting

Microsoft Teams webhooks are limited to 4 requests per second. If you exceed this limit:

1. The server will automatically handle retries with exponential backoff
2. Consider using batch operations where appropriate
3. Monitor the server logs for rate limiting messages

## Limitations

- Maximum message size is 28 KB
- Rate limited to 4 requests per second
- Cannot edit messages after they are sent
- Adaptive Cards in MS Teams support a subset of the full Adaptive Card schema
- Simple text messages have the best compatibility across all Teams clients

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

Built with ❤️ by Al Amin