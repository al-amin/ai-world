"""
Main entry point for running the MCP Teams Webhook server.
"""

import asyncio
from .server import run_server

if __name__ == "__main__":
    asyncio.run(run_server())
EOF < /dev/null