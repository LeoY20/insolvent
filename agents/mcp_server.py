
import sys
import os

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from dedalus_mcp import MCPServer
from agents.dedalus_tools import delete_redundant_entries

# Create the server
server = MCPServer("pharma-sentinel-tools")

# Register the tool
server.collect(delete_redundant_entries)

if __name__ == "__main__":
    # Start the server on localhost:8000/mcp
    print("Starting MCP Server on http://127.0.0.1:8000/mcp...")
    asyncio.run(server.serve())
