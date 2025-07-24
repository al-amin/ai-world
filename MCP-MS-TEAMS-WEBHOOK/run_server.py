#!/usr/bin/env python3
"""
Run the MCP Teams Webhook server from the command line.

This script adds the src directory to the Python path and runs the server.
"""

import asyncio
import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mcp_teams_webhook.server import run_server

if __name__ == "__main__":
    # Run the server with stdio transport by default
    asyncio.run(run_server("stdio"))